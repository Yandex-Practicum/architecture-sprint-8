from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow_clickhouse_plugin.hooks.clickhouse import ClickHouseHook 
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from clickhouse_driver import Client
import pandas as pd
import logging
import csv


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=1),
}

def load_csv_to_clickhouse(**context):
    """Загрузка данных из CSV файла в ClickHouse"""
    ch_hook = ClickHouseHook(clickhouse_conn_id='olap_db')
    
    # Проверяем, есть ли уже данные
    result = ch_hook.execute("SELECT count(*) FROM emg_sensor_data")
    count = result[0][0] if result else 0
    
    if count == 0:
        logging.info("Loading data from CSV file...")
        
        # Загружаем данные из CSV
        ch_hook.execute("""
            INSERT INTO emg_sensor_data
            SELECT * FROM file('olap.csv', 'CSVWithNames')
        """)
        
        # Проверяем результат
        result = ch_hook.execute("SELECT count(*) FROM emg_sensor_data")
        new_count = result[0][0] if result else 0
        logging.info(f"Loaded {new_count} records from CSV")
    else:
        logging.info(f"Table already contains {count} records, skipping CSV load")
        
def generate_insert_queries_to_crm():
    CSV_FILE_PATH = './dags/data/crm.csv'
    with open( CSV_FILE_PATH, 'r') as csvfile:
        csvreader = csv.reader(csvfile)
    
        # Генерим запросы
        insert_queries = []
        is_header = True
        for row in csvreader:
            if is_header:
                is_header = False
                continue
            name = row[1].replace("'", "''")
            email = row[2].replace("'", "''")
            country = row[4].replace("'", "''")
            address = row[5].replace("'", "''")
            phone = row[6].replace("'", "''")
            
            # Используем форматирование с явными переменными
            insert_query = (
                f"INSERT INTO customers (id, name, email, age, country, address, phone) "
                f"VALUES ({row[0]}, '{name}', '{email}', {row[3]}, '{country}', '{address}', '{phone}');"
            )
            
            insert_queries.append(insert_query)
        
        # Сохраняем запросы
        with open('./dags/sql/insert_queries_to_crm.sql', 'w') as f:
            for query in insert_queries:
                f.write(f"{query}\n")
    

def extract_crm_data(**context):
    """Извлечение данных из CRM PostgreSQL с использованием SQLAlchemy"""
    # Получаем параметры подключения из Airflow connection
    pg_hook = PostgresHook(postgres_conn_id='crm_db')
    
    conn = pg_hook.get_conn()
    
    query = """
    SELECT 
        id,
        name,
        email,
        age,
        gender,
        country,
        address,
        phone
    FROM customers
    """
    
    df = pd.read_sql(query, conn)
    
    # Сохраняем в XCom
    context['task_instance'].xcom_push(key='crm_data', value=df.to_json())
    logging.info(f"Extracted {len(df)} customers from CRM")
    
    return len(df)

def extract_telemetry_data(**context):
    """Извлечение данных телеметрии из ClickHouse с использованием clickhouse-driver"""
    # Получаем параметры подключения из Airflow connection
    ch_hook = ClickHouseHook(clickhouse_conn_id='olap_db')
    
    # Извлекаем параметры подключения
    #conn_params = {
    #    'host': ch_hook.host,
    #    'port': ch_hook.port,
    #    'user': ch_hook.username,
    #    'password': ch_hook.password or '',
    #    'database': ch_hook.schema or 'default',
    #}
    
    # Создаем клиент clickhouse-driver
    #client = Client(**conn_params)
    
    query = """
    SELECT 
        user_id,
        prosthesis_type,
        muscle_group,
        signal_frequency,
        signal_duration,
        signal_amplitude,
        signal_time
    FROM emg_sensor_data
    """
    
    # Выполняем запрос и получаем данные
    #result = client.execute(query, with_column_types=True)
    data = ch_hook.execute(query)
    column_names = [
        'user_id', 
        'prosthesis_type', 
        'muscle_group', 
        'signal_frequency', 
        'signal_duration', 
        'signal_amplitude', 
        'signal_time'
    ]
    
    # Преобразуем в pandas DataFrame    
    if data:
        df = pd.DataFrame(data, columns=column_names)
        logging.info(f"Extracted {len(df)} telemetry records from ClickHouse")
    else:
        logging.warning("No telemetry data found")
        df = pd.DataFrame(columns=column_names)
    
    logging.info(f"Extracted {len(df)} telemetry records from ClickHouse")
    
    # Сохраняем в XCom
    context['task_instance'].xcom_push(key='telemetry_data', value=df.to_json())
    
    #client.disconnect()
    return len(df)

def transform_and_build_mart(**context):
    """Трансформация данных и построение витрины"""
    ti = context['task_instance']
    
    # Получаем данные из XCom
    crm_json = ti.xcom_pull(key='crm_data', task_ids='extract_crm')
    telemetry_json = ti.xcom_pull(key='telemetry_data', task_ids='extract_telemetry')
    
    crm_df = pd.read_json(crm_json)
    telemetry_df = pd.read_json(telemetry_json)
    
    # Агрегация телеметрии по пользователям
    telemetry_agg = telemetry_df.groupby(['user_id', 'prosthesis_type']).agg({
        'signal_duration': ['count', 'sum'],
        'signal_frequency': 'mean',
        'signal_amplitude': 'mean',
        'signal_time': 'max'
    }).reset_index()
    
    # Переименовываем колонки
    telemetry_agg.columns = [
        'user_id', 'prosthesis_type',
        'total_sessions', 'total_signal_duration',
        'avg_signal_frequency', 'avg_signal_amplitude',
        'last_signal_time'
    ]
    
    # Объединяем с CRM данными
    mart_df = pd.merge(
        crm_df,
        telemetry_agg,
        left_on='id',
        right_on='user_id',
        how='inner'
    )
    
    # Выбираем нужные колонки для витрины
    result_df = mart_df[[
        'user_id', 'name', 'email', 'age', 'gender', 'country',
        'prosthesis_type', 'total_sessions', 'total_signal_duration',
        'avg_signal_frequency', 'avg_signal_amplitude', 'last_signal_time'
    ]]
    
    context['task_instance'].xcom_push(key='mart_data', value=result_df.to_json())
    logging.info(f"Built mart with {len(result_df)} records")
    
    return len(result_df)

def load_mart_to_clickhouse(**context):
    """Загрузка витрины в ClickHouse"""
    ti = context['task_instance']
    mart_json = ti.xcom_pull(key='mart_data', task_ids='transform_and_build_mart')
    
    if not mart_json:
        raise ValueError("No mart data to load")
    
    mart_df = pd.read_json(mart_json)
    
    ch_hook = ClickHouseHook(clickhouse_conn_id='olap_db')
    
    # Очищаем предыдущие данные (опционально)
    ch_hook.execute("TRUNCATE TABLE IF EXISTS customer_report_final")
    
    # Вставляем новые данные
    for _, row in mart_df.iterrows():
        insert_query = """
        INSERT INTO customer_report_final (
            user_id, name, email, age, gender, country,
            prosthesis_type, total_sessions, total_signal_duration,
            avg_signal_frequency, avg_signal_amplitude, last_signal_time,
            updated_at
        ) VALUES (
            %(user_id)s, %(name)s, %(email)s, %(age)s, %(gender)s, %(country)s,
            %(prosthesis_type)s, %(total_sessions)s, %(total_signal_duration)s,
            %(avg_signal_frequency)s, %(avg_signal_amplitude)s, %(last_signal_time)s,
            now()
        )
        """
        ch_hook.execute(insert_query, row.to_dict())
    
    logging.info(f"Loaded {len(mart_df)} records to customer_report_final")

def update_materialized_view(**context):
    """Обновление материализованного представления (если используем агрегацию на стороне ClickHouse)"""
    ch_hook = ClickHouseHook(clickhouse_conn_id='olap_db')
    
    # Если вы используете материализованное представление, можно его обновить
    # В ClickHouse материализованные представления обновляются автоматически при вставке,
    # но если вы хотите пересчитать вручную:
    # ch_hook.run("TRUNCATE TABLE customer_report")
    # ch_hook.run("INSERT INTO customer_report SELECT * FROM customer_report_final FINAL")
    
    logging.info("Materialized view updated")

# Создаем DAG
with DAG(
    'crm_to_clickhouse_mart',
    default_args=default_args,
    description='ETL from CRM PostgreSQL to ClickHouse mart',
    schedule_interval='0 3 * * *',  # Каждый день в 3:00
    catchup=False,
    tags=['crm', 'clickhouse', 'mart'],
) as dag:

    extract_crm = PythonOperator(
        task_id='extract_crm',
        python_callable=extract_crm_data,
        provide_context=True,
    )

    extract_telemetry = PythonOperator(
        task_id='extract_telemetry',
        python_callable=extract_telemetry_data,
        provide_context=True,
    )

    transform_and_build = PythonOperator(
        task_id='transform_and_build_mart',
        python_callable=transform_and_build_mart,
        provide_context=True,
    )

    load_mart = PythonOperator(
        task_id='load_mart_to_clickhouse',
        python_callable=load_mart_to_clickhouse,
        provide_context=True,
    )

    update_view = PythonOperator(
        task_id='update_materialized_view',
        python_callable=update_materialized_view,
        provide_context=True,
    )
    
    load_csv = PythonOperator(
        task_id='load_csv_to_clickhouse',
        python_callable=load_csv_to_clickhouse,
        provide_context=True,
    )
    
    generate_insert_queries_to_crm = PythonOperator(
    task_id='generate_insert_queries_to_crm',
    python_callable=generate_insert_queries_to_crm
    )
    
    create_table_to_crm = PostgresOperator(
        task_id='create_table_to_crm', #идентификатор задачи
        postgres_conn_id='crm_db',  # Название подключения
        sql="""
        DROP TABLE IF EXISTS customers;
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100),
            age NUMERIC,
            gender VARCHAR(10),
            country VARCHAR(100),
            address VARCHAR(255),
            phone VARCHAR(255)
        );
        """
    )
    
    run_insert_queries_to_crm = PostgresOperator(
        task_id='run_insert_queries',
        postgres_conn_id='crm_db',  # Название подключения к PostgreSQL в Airflow UI
        sql='sql/insert_queries_to_crm.sql'
    )

    # Определяем порядок выполнения
    [load_csv, create_table_to_crm ] >> generate_insert_queries_to_crm >> run_insert_queries_to_crm >> extract_crm >> extract_telemetry >> transform_and_build >> load_mart >> update_view