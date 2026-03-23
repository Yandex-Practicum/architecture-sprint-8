from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow_clickhouse_plugin.hooks.clickhouse import ClickHouseHook  # Изменен путь импорта!
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import pandas as pd
import logging
import os

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def extract_crm_data(**context):
    """Извлечение данных из CRM PostgreSQL"""
    tmp_file = '/tmp/crm_data.csv'
    try:
        # Подключение к PostgreSQL CRM
        pg_hook = PostgresHook(postgres_conn_id='crm_postgres_conn')
        
        # SQL запрос для получения данных CRM
        sql = """
        SELECT 
            id as user_id,
            name as full_name,
            email,
            age,
            gender,
            country,
            address,
            phone
        FROM customers
        WHERE updated_at >= COALESCE(
            (SELECT last_value FROM airflow_metadata.crm_last_extract),
            '1970-01-01'
        )
        """
        
        # Выполняем запрос и получаем DataFrame
        df = pg_hook.get_pandas_df(sql)
        
        # Сохраняем во временный файл для передачи в следующие задачи
        df.to_csv(tmp_file, index=False)
        
        # Сохраняем метаданные о количестве записей
        context['ti'].xcom_push(key='crm_records_count', value=len(df))
        
        logging.info(f"Extracted {len(df)} records from CRM")
        
    except Exception as e:
        logging.error(f"Error extracting CRM data: {str(e)}")
        # Удаляем временный файл в случае ошибки
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
        raise

def extract_telemetry_data(**context):
    """Извлечение данных телеметрии из ClickHouse"""
    tmp_file = '/tmp/telemetry_data.csv'
    try:
        # Подключение к ClickHouse
        ch_hook = ClickHouseHook(clickhouse_conn_id='clickhouse_conn')
        
        # SQL запрос для получения новых данных телеметрии
        sql = """
        SELECT 
            user_id,
            prosthesis_type,
            muscle_group,
            signal_frequency,
            signal_duration,
            signal_amplitude,
            signal_time
        FROM emg_sensor_data
        WHERE signal_time >= COALESCE(
            (SELECT max(last_signal_time) FROM report_mart),
            toDateTime('1970-01-01')
        )
        """
        
        # Выполняем запрос и получаем результат (используем execute)
        result = ch_hook.execute(sql)
        
        # Преобразуем в DataFrame
        if result:
            df = pd.DataFrame(result, columns=[
                'user_id', 'prosthesis_type', 'muscle_group', 
                'signal_frequency', 'signal_duration', 'signal_amplitude', 'signal_time'
            ])
        else:
            df = pd.DataFrame()
        
        df.to_csv(tmp_file, index=False)
        
        context['ti'].xcom_push(key='telemetry_records_count', value=len(df))
        
        logging.info(f"Extracted {len(df)} records from telemetry")
        
    except Exception as e:
        logging.error(f"Error extracting telemetry data: {str(e)}")
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
        raise

def transform_and_load_data(**context):
    """Трансформация данных и загрузка в витрину"""
    crm_file = '/tmp/crm_data.csv'
    telemetry_file = '/tmp/telemetry_data.csv'
    
    try:
        # Проверяем существование файлов
        if not os.path.exists(crm_file) or not os.path.exists(telemetry_file):
            logging.error("Data files not found")
            raise FileNotFoundError("CRM or telemetry data files missing")
        
        # Загружаем данные из временных файлов
        crm_df = pd.read_csv(crm_file)
        telemetry_df = pd.read_csv(telemetry_file)
        
        if len(telemetry_df) == 0:
            logging.info("No new telemetry data to process")
            return
        
        # Подключаемся к ClickHouse
        ch_hook = ClickHouseHook(clickhouse_conn_id='clickhouse_conn')
        
        # Агрегируем данные телеметрии по пользователям и типам протезов
        agg_df = telemetry_df.groupby(['user_id', 'prosthesis_type']).agg({
            'signal_duration': ['count', 'sum', 'mean'],
            'signal_frequency': 'mean',
            'signal_amplitude': 'mean',
            'signal_time': 'max'
        }).reset_index()
        
        # Переименовываем колонки
        agg_df.columns = [
            'user_id', 'prosthesis_type',
            'total_sessions', 'total_signal_duration', 'avg_signal_duration',
            'avg_signal_frequency', 'avg_signal_amplitude', 'last_signal_time'
        ]
        
        # Объединяем с данными CRM
        result_df = pd.merge(agg_df, crm_df, on='user_id', how='inner')
        
        if len(result_df) == 0:
            logging.warning("No matching records after merge")
            return
        
        # Загружаем в витрину (батчами для производительности)
        batch_size = 1000
        for i in range(0, len(result_df), batch_size):
            batch = result_df.iloc[i:i+batch_size]
            
            # Формируем список значений для батчевой вставки
            values_list = []
            for _, row in batch.iterrows():
                values_list.append(f"({row['user_id']}, '{row['full_name']}', '{row['email']}', {row['age']}, '{row['gender']}', '{row['country']}', '{row['prosthesis_type']}', {int(row['total_sessions'])}, {int(row['total_signal_duration'])}, {float(row['avg_signal_frequency'])}, {float(row['avg_signal_amplitude'])}, '{row['last_signal_time']}')")
            
            # Выполняем батчевую вставку
            if values_list:
                insert_sql = f"""
                INSERT INTO report_mart (
                    user_id, full_name, email, age, gender, country,
                    prosthesis_type, total_sessions, total_signal_duration,
                    avg_signal_frequency, avg_signal_amplitude, last_signal_time
                ) VALUES ы
                {','.join(values_list)}
                """
                
                ch_hook.execute(insert_sql)
        
        logging.info(f"Loaded {len(result_df)} records to report_mart")
        
        
        # Оптимизируем таблицу
        ch_hook.run("OPTIMIZE TABLE report_mart FINAL")
        
        # Очищаем временные файлы после успешной загрузки
        os.remove(crm_file)
        os.remove(telemetry_file)
        
    except Exception as e:
        logging.error(f"Error in transform and load: {str(e)}")
        raise

def update_crm_extract_metadata(**context):
    """Обновление метаданных о последнем извлечении из CRM"""
    try:
        pg_hook = PostgresHook(postgres_conn_id='crm_postgres_conn')
        
        # Создаем схему для метаданных, если не существует
        pg_hook.run("""
        CREATE SCHEMA IF NOT EXISTS airflow_metadata;
        
        CREATE TABLE IF NOT EXISTS airflow_metadata.crm_last_extract (
            last_value TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        TRUNCATE TABLE airflow_metadata.crm_last_extract;
        
        INSERT INTO airflow_metadata.crm_last_extract (last_value)
        VALUES (CURRENT_TIMESTAMP);
        """)
        
        logging.info("CRM metadata updated successfully")
        
    except Exception as e:
        logging.error(f"Error updating metadata: {str(e)}")
        raise

def check_data_quality(**context):
    """Проверка качества данных"""
    try:
        crm_count = context['ti'].xcom_pull(key='crm_records_count', task_ids='extract_crm_data')
        telemetry_count = context['ti'].xcom_pull(key='telemetry_records_count', task_ids='extract_telemetry_data')
        
        if crm_count is None:
            crm_count = 0
            
        if telemetry_count is None:
            telemetry_count = 0
        
        if crm_count == 0:
            logging.warning("No CRM data extracted")
        
        if telemetry_count == 0:
            logging.warning("No telemetry data extracted")
        
        if telemetry_count > 0 and crm_count == 0:
            # Если есть телеметрия без данных CRM, возможно проблема
            logging.error("Telemetry data without matching CRM records")
            raise ValueError("Data quality check failed: missing CRM data")
        
        logging.info(f"Data quality check passed: CRM={crm_count}, Telemetry={telemetry_count}")
        
        # Передаем результат дальше
        context['ti'].xcom_push(key='quality_check_passed', value=True)
        
    except Exception as e:
        logging.error(f"Data quality check failed: {str(e)}")
        context['ti'].xcom_push(key='quality_check_passed', value=False)
        raise

def create_clickhouse_tables_func(**context):
    """Создание таблиц в ClickHouse через PythonOperator"""
    try:
        ch_hook = ClickHouseHook(clickhouse_conn_id='clickhouse_conn')
        
        # Создаем таблицу emg_sensor_data (таблица телеметрии)
        create_emg_table = """
        CREATE TABLE IF NOT EXISTS emg_sensor_data (
            user_id UInt32,
            prosthesis_type String,
            muscle_group String,
            signal_frequency Float64,
            signal_duration UInt32,
            signal_amplitude Float64,
            signal_time DateTime
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(signal_time)
        ORDER BY (user_id, signal_time);
        """
        
        # Создаем витрину report_mart
        create_report_mart = """
        CREATE TABLE IF NOT EXISTS report_mart (
            user_id UInt32,
            full_name String,
            email String,
            age UInt8,
            gender String,
            country String,
            prosthesis_type String,
            total_sessions UInt32,
            total_signal_duration UInt64,
            avg_signal_frequency Float64,
            avg_signal_amplitude Float64,
            last_signal_time DateTime,
            updated_at DateTime DEFAULT now()
        ) ENGINE = SummingMergeTree()
        PARTITION BY toYYYYMM(last_signal_time)
        ORDER BY (user_id, prosthesis_type, last_signal_time);
        """
        
        # Выполняем создание таблиц (используем execute вместо run)
        logging.info("Creating table emg_sensor_data...")
        ch_hook.execute(create_emg_table)
        
        logging.info("Creating table report_mart...")
        ch_hook.execute(create_report_mart)
        
        logging.info("ClickHouse tables created successfully")
        
    except Exception as e:
        logging.error(f"Error creating ClickHouse tables: {str(e)}")
        raise


# Создание DAG
with DAG(
    'etl_to_clickhouse_dag',
    default_args=default_args,
    description='ETL process from CRM and telemetry to ClickHouse report mart',
    schedule_interval='0 3 * * *',  # Запуск каждый день в 3:00
    catchup=False,
    tags=['etl', 'clickhouse', 'reports'],
    max_active_runs=1,  # Только один активный запуск
) as dag:

    # Создание таблиц в ClickHouse (если не существуют)
    create_clickhouse_tables = PythonOperator(
        task_id='create_clickhouse_tables',
        python_callable=create_clickhouse_tables_func,
        provide_context=True
    )

    # Задачи ETL
    extract_crm = PythonOperator(
        task_id='extract_crm_data',
        python_callable=extract_crm_data,
        provide_context=True
    )

    extract_telemetry = PythonOperator(
        task_id='extract_telemetry_data',
        python_callable=extract_telemetry_data,
        provide_context=True
    )

    quality_check = PythonOperator(
        task_id='check_data_quality',
        python_callable=check_data_quality,
        provide_context=True
    )

    transform_load = PythonOperator(
        task_id='transform_and_load_data',
        python_callable=transform_and_load_data,
        provide_context=True
    )

    update_metadata = PythonOperator(
        task_id='update_crm_extract_metadata',
        python_callable=update_crm_extract_metadata,
        provide_context=True
    )

    # Порядок выполнения задач
    create_clickhouse_tables >> [extract_crm, extract_telemetry] >> quality_check >> transform_load >> update_metadata