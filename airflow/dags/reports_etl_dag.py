"""
ETL DAG для объединения данных из CRM и телеметрии в витрину отчётности
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.hooks.http import HttpHook

try:
    import clickhouse_connect
except ImportError:
    clickhouse_connect = None
    print("Warning: clickhouse-connect not installed")

# Параметры по умолчанию
default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Создание DAG
dag = DAG(
    'reports_etl_dag',
    default_args=default_args,
    description='ETL процесс для подготовки витрины отчётности',
    schedule_interval='0 2 * * *',  # Запуск каждый день в 2:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['reports', 'etl', 'crm', 'telemetry'],
)

def extract_crm_data(**context):
    """
    Извлечение данных о клиентах из CRM системы
    В реальном сценарии здесь будет API вызов к Битрикс24
    """
    # Имитация извлечения данных из CRM
    # В реальности здесь будет HTTP запрос к API Битрикс24
    http_hook = HttpHook(http_conn_id='crm_api', method='GET')
    
    # Пример структуры данных из CRM
    crm_data = [
        {
            'user_id': 'user1',
            'email': 'user1@example.com',
            'first_name': 'User',
            'last_name': 'One',
            'prosthesis_id': 'prosthesis_001',
            'order_date': '2024-01-15',
            'country': 'RU'
        },
        {
            'user_id': 'user2',
            'email': 'user2@example.com',
            'first_name': 'User',
            'last_name': 'Two',
            'prosthesis_id': 'prosthesis_002',
            'order_date': '2024-02-20',
            'country': 'RU'
        },
        {
            'user_id': 'prothetic1',
            'email': 'prothetic1@example.com',
            'first_name': 'Prothetic',
            'last_name': 'One',
            'prosthesis_id': 'prosthesis_003',
            'order_date': '2024-03-10',
            'country': 'RU'
        }
    ]
    
    # Сохраняем данные в XCom для следующего шага
    context['ti'].xcom_push(key='crm_data', value=crm_data)
    return crm_data

def extract_telemetry_data(**context):
    """
    Извлечение данных телеметрии из PostgreSQL
    """
    postgres_hook = PostgresHook(postgres_conn_id='postgres_default')
    
    # SQL запрос для извлечения агрегированной телеметрии
    sql_query = """
    SELECT 
        user_id,
        prosthesis_id,
        DATE(timestamp) as date,
        COUNT(*) as total_actions,
        AVG(response_time_ms) as avg_response_time,
        MAX(response_time_ms) as max_response_time,
        MIN(response_time_ms) as min_response_time,
        SUM(CASE WHEN action_type = 'grasp' THEN 1 ELSE 0 END) as grasp_count,
        SUM(CASE WHEN action_type = 'release' THEN 1 ELSE 0 END) as release_count,
        SUM(CASE WHEN action_type = 'flex' THEN 1 ELSE 0 END) as flex_count,
        AVG(battery_level) as avg_battery_level,
        AVG(signal_quality) as avg_signal_quality
    FROM telemetry_data
    WHERE timestamp >= CURRENT_DATE - INTERVAL '1 day'
    GROUP BY user_id, prosthesis_id, DATE(timestamp)
    ORDER BY date DESC, user_id;
    """
    
    # Выполняем запрос
    connection = postgres_hook.get_conn()
    cursor = connection.cursor()
    cursor.execute(sql_query)
    
    columns = [desc[0] for desc in cursor.description]
    telemetry_data = []
    for row in cursor.fetchall():
        telemetry_data.append(dict(zip(columns, row)))
    
    cursor.close()
    connection.close()
    
    # Сохраняем данные в XCom
    context['ti'].xcom_push(key='telemetry_data', value=telemetry_data)
    return telemetry_data

def transform_and_load(**context):
    """
    Объединение данных из CRM и телеметрии и загрузка в ClickHouse
    """
    # Получаем данные из предыдущих шагов
    crm_data = context['ti'].xcom_pull(key='crm_data', task_ids='extract_crm_data')
    telemetry_data = context['ti'].xcom_pull(key='telemetry_data', task_ids='extract_telemetry_data')
    
    # Создаём словарь для быстрого поиска данных CRM по user_id
    crm_dict = {item['user_id']: item for item in crm_data}
    
    # Объединяем данные
    report_data = []
    for telemetry in telemetry_data:
        user_id = telemetry.get('user_id')
        if user_id in crm_dict:
            crm_info = crm_dict[user_id]
            report_row = {
                'user_id': user_id,
                'email': crm_info.get('email'),
                'first_name': crm_info.get('first_name'),
                'last_name': crm_info.get('last_name'),
                'prosthesis_id': telemetry.get('prosthesis_id'),
                'report_date': telemetry.get('date'),
                'total_actions': telemetry.get('total_actions', 0),
                'avg_response_time': telemetry.get('avg_response_time', 0),
                'max_response_time': telemetry.get('max_response_time', 0),
                'min_response_time': telemetry.get('min_response_time', 0),
                'grasp_count': telemetry.get('grasp_count', 0),
                'release_count': telemetry.get('release_count', 0),
                'flex_count': telemetry.get('flex_count', 0),
                'avg_battery_level': telemetry.get('avg_battery_level', 0),
                'avg_signal_quality': telemetry.get('avg_signal_quality', 0),
                'country': crm_info.get('country', 'RU'),
                'order_date': crm_info.get('order_date'),
                'processed_at': datetime.now().isoformat()
            }
            report_data.append(report_row)
    
    # Подключение к ClickHouse
    if clickhouse_connect is None:
        raise ImportError("clickhouse-connect package is required")
    
    client = clickhouse_connect.get_client(
        host='clickhouse',
        port=8123,
        username='default',
        password=''
    )
    
    # Создание таблицы витрины, если её нет
    create_table_query = """
    CREATE TABLE IF NOT EXISTS reports_mart
    (
        user_id String,
        email String,
        first_name String,
        last_name String,
        prosthesis_id String,
        report_date Date,
        total_actions UInt32,
        avg_response_time Float32,
        max_response_time Float32,
        min_response_time Float32,
        grasp_count UInt32,
        release_count UInt32,
        flex_count UInt32,
        avg_battery_level Float32,
        avg_signal_quality Float32,
        country String,
        order_date String,
        processed_at DateTime
    )
    ENGINE = MergeTree()
    PARTITION BY toYYYYMM(report_date)
    ORDER BY (user_id, report_date, prosthesis_id)
    """
    
    client.command(create_table_query)
    
    # Загрузка данных в ClickHouse
    if report_data:
        client.insert('reports_mart', report_data)
        print(f"Загружено {len(report_data)} записей в витрину отчётности")
    else:
        print("Нет данных для загрузки")
    
    return len(report_data)

# Определение задач
extract_crm_task = PythonOperator(
    task_id='extract_crm_data',
    python_callable=extract_crm_data,
    dag=dag,
)

extract_telemetry_task = PythonOperator(
    task_id='extract_telemetry_data',
    python_callable=extract_telemetry_data,
    dag=dag,
)

transform_load_task = PythonOperator(
    task_id='transform_and_load',
    python_callable=transform_and_load,
    dag=dag,
)

# Определение зависимостей
[extract_crm_task, extract_telemetry_task] >> transform_load_task
