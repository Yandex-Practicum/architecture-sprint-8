"""
Airflow DAG для ETL-процесса системы отчётов BionicPRO

Этот DAG выполняет:
1. Extract: Извлечение данных из PostgreSQL (данные датчиков) и CSV файлов (CRM данные)
2. Transform: Объединение, очистка и агрегация данных по пользователям
3. Load: Загрузка агрегированных данных в ClickHouse (OLAP Data Warehouse)

Расписание: Ежедневно в 2:00 UTC
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
import pandas as pd
import psycopg2
from clickhouse_driver import Client
import os
from pathlib import Path

# Параметры подключения (должны быть в Airflow Variables или Connections)
POSTGRES_CONN_ID = 'postgres_sensors'  # Connection для PostgreSQL с данными датчиков
CLICKHOUSE_HOST = 'clickhouse'  # Имя сервиса из docker-compose
CLICKHOUSE_PORT = 9000
CLICKHOUSE_DATABASE = 'bionicpro_reports'
CLICKHOUSE_USER = 'default'
CLICKHOUSE_PASSWORD = 'clickhouse_password'
CSV_DATA_PATH = '/data/crm'  # Путь к CSV файлам с данными CRM

# Структура витрины отчётности
DATA_MART_TABLE = 'user_reports_mart'

default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': days_ago(1),
}

dag = DAG(
    'reports_etl_dag',
    default_args=default_args,
    description='ETL процесс для подготовки витрины отчётности BionicPRO',
    schedule_interval='0 2 * * *',  # Ежедневно в 2:00 UTC
    catchup=False,
    tags=['reports', 'etl', 'bionicpro'],
)


def extract_sensor_data(**context):
    """
    Извлекает данные с датчиков из PostgreSQL за последний день
    """
    execution_date = context['execution_date']
    start_date = execution_date - timedelta(days=1)
    end_date = execution_date
    
    # Подключение к PostgreSQL
    from airflow.hooks.postgres_hook import PostgresHook
    postgres_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    
    query = """
    SELECT 
        user_id,
        device_id,
        timestamp,
        sensor_type,
        sensor_value,
        movement_type,
        movement_count,
        usage_duration_seconds
    FROM sensor_telemetry
    WHERE timestamp >= %s AND timestamp < %s
    ORDER BY user_id, timestamp
    """
    
    df = postgres_hook.get_pandas_sql(query, parameters=[start_date, end_date])
    
    # Сохраняем во временный файл для следующего шага
    output_path = f'/tmp/sensor_data_{execution_date.strftime("%Y%m%d")}.parquet'
    df.to_parquet(output_path, index=False)
    
    print(f"Извлечено {len(df)} записей данных датчиков за период {start_date} - {end_date}")
    return output_path


def extract_crm_data(**context):
    """
    Извлекает данные из CSV файлов CRM
    """
    execution_date = context['execution_date']
    
    # Путь к CSV файлам
    csv_path = Path(CSV_DATA_PATH)
    
    # Список CSV файлов для обработки
    csv_files = {
        'users': csv_path / 'users.csv',
        'orders': csv_path / 'orders.csv',
        'maintenance': csv_path / 'maintenance_history.csv',
    }
    
    crm_data = {}
    
    for data_type, file_path in csv_files.items():
        if file_path.exists():
            df = pd.read_csv(file_path)
            output_path = f'/tmp/crm_{data_type}_{execution_date.strftime("%Y%m%d")}.parquet'
            df.to_parquet(output_path, index=False)
            crm_data[data_type] = output_path
            print(f"Извлечено {len(df)} записей из {data_type}")
        else:
            print(f"Предупреждение: файл {file_path} не найден")
    
    return crm_data


def transform_and_aggregate(**context):
    """
    Трансформирует и объединяет данные из разных источников
    Группирует аналитику по телеметрии в разрезе клиентов
    """
    execution_date = context['execution_date']
    ti = context['ti']
    
    # Получаем пути к данным из предыдущих задач
    sensor_data_path = ti.xcom_pull(task_ids='extract_sensor_data')
    crm_data = ti.xcom_pull(task_ids='extract_crm_data')
    
    # Загружаем данные датчиков
    sensor_df = pd.read_parquet(sensor_data_path)
    
    # Загружаем данные CRM
    users_df = pd.read_parquet(crm_data['users']) if 'users' in crm_data else pd.DataFrame()
    orders_df = pd.read_parquet(crm_data['orders']) if 'orders' in crm_data else pd.DataFrame()
    maintenance_df = pd.read_parquet(crm_data['maintenance']) if 'maintenance' in crm_data else pd.DataFrame()
    
    # Трансформация данных датчиков - агрегация по пользователям
    sensor_df['timestamp'] = pd.to_datetime(sensor_df['timestamp'])
    sensor_df['date'] = sensor_df['timestamp'].dt.date
    sensor_df['hour'] = sensor_df['timestamp'].dt.hour
    
    # Агрегация данных телеметрии по пользователям и датам
    telemetry_agg = sensor_df.groupby(['user_id', 'date']).agg({
        'usage_duration_seconds': 'sum',
        'movement_count': 'sum',
        'sensor_value': ['mean', 'min', 'max'],
        'device_id': 'first',  # Берем первый device_id для пользователя за день
    }).reset_index()
    
    # Упрощаем имена колонок после агрегации
    telemetry_agg.columns = [
        'user_id', 'date', 'total_usage_seconds', 'total_movements',
        'avg_sensor_value', 'min_sensor_value', 'max_sensor_value', 'device_id'
    ]
    
    # Объединение с данными CRM
    if not users_df.empty:
        # Объединяем с данными пользователей
        result_df = telemetry_agg.merge(
            users_df[['user_id', 'user_name', 'prosthesis_install_date', 'prosthesis_type']],
            on='user_id',
            how='left'
        )
    else:
        result_df = telemetry_agg.copy()
        result_df['user_name'] = None
        result_df['prosthesis_install_date'] = None
        result_df['prosthesis_type'] = None
    
    # Добавляем информацию о заказах
    if not orders_df.empty:
        # Берем последний заказ для каждого пользователя
        latest_orders = orders_df.sort_values('order_date').groupby('user_id').last().reset_index()
        result_df = result_df.merge(
            latest_orders[['user_id', 'order_date', 'order_status']],
            on='user_id',
            how='left',
            suffixes=('', '_order')
        )
    
    # Добавляем информацию о последнем обслуживании
    if not maintenance_df.empty:
        latest_maintenance = maintenance_df.sort_values('maintenance_date').groupby('user_id').last().reset_index()
        result_df = result_df.merge(
            latest_maintenance[['user_id', 'maintenance_date', 'maintenance_type', 'maintenance_status']],
            on='user_id',
            how='left'
        )
    
    # Добавляем вычисляемые поля
    result_df['date'] = pd.to_datetime(result_df['date'])
    result_df['usage_hours'] = result_df['total_usage_seconds'] / 3600
    result_df['year'] = result_df['date'].dt.year
    result_df['month'] = result_df['date'].dt.month
    result_df['week'] = result_df['date'].dt.isocalendar().week
    result_df['day_of_week'] = result_df['date'].dt.dayofweek
    
    # Добавляем метаданные обработки
    result_df['processed_at'] = execution_date
    result_df['data_period_start'] = execution_date - timedelta(days=1)
    result_df['data_period_end'] = execution_date
    
    # Сохраняем результат
    output_path = f'/tmp/transformed_data_{execution_date.strftime("%Y%m%d")}.parquet'
    result_df.to_parquet(output_path, index=False)
    
    print(f"Трансформировано и объединено {len(result_df)} записей")
    print(f"Уникальных пользователей: {result_df['user_id'].nunique()}")
    
    return output_path


def load_to_clickhouse(**context):
    """
    Загружает трансформированные данные в ClickHouse (OLAP Data Warehouse)
    """
    execution_date = context['execution_date']
    ti = context['ti']
    
    # Получаем путь к трансформированным данным
    transformed_data_path = ti.xcom_pull(task_ids='transform_and_aggregate')
    
    # Загружаем данные
    df = pd.read_parquet(transformed_data_path)
    
    # Подключение к ClickHouse
    client = Client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DATABASE,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD
    )
    
    # Создаем таблицу витрины, если её нет
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS {DATA_MART_TABLE}
    (
        user_id UInt64,
        date Date,
        device_id String,
        total_usage_seconds UInt32,
        total_movements UInt32,
        avg_sensor_value Float32,
        min_sensor_value Float32,
        max_sensor_value Float32,
        usage_hours Float32,
        year UInt16,
        month UInt8,
        week UInt8,
        day_of_week UInt8,
        user_name Nullable(String),
        prosthesis_install_date Nullable(Date),
        prosthesis_type Nullable(String),
        order_date Nullable(Date),
        order_status Nullable(String),
        maintenance_date Nullable(Date),
        maintenance_type Nullable(String),
        maintenance_status Nullable(String),
        processed_at DateTime,
        data_period_start DateTime,
        data_period_end DateTime
    )
    ENGINE = MergeTree()
    PARTITION BY toYYYYMM(date)
    ORDER BY (user_id, date)
    SETTINGS index_granularity = 8192
    """
    
    client.execute(create_table_query)
    print(f"Таблица {DATA_MART_TABLE} создана или уже существует")
    
    # Подготовка данных для вставки
    # Удаляем дубликаты по user_id и date (если есть)
    df = df.drop_duplicates(subset=['user_id', 'date'], keep='last')
    
    # Заполняем пропущенные значения для числовых полей
    numeric_columns = ['total_usage_seconds', 'total_movements', 'avg_sensor_value', 
                      'min_sensor_value', 'max_sensor_value', 'usage_hours']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    
    # Конвертируем данные в формат для ClickHouse
    data_to_insert = []
    for _, row in df.iterrows():
        data_to_insert.append((
            int(row['user_id']),
            row['date'].date() if pd.notna(row['date']) else None,
            str(row['device_id']) if pd.notna(row['device_id']) else '',
            int(row['total_usage_seconds']) if pd.notna(row['total_usage_seconds']) else 0,
            int(row['total_movements']) if pd.notna(row['total_movements']) else 0,
            float(row['avg_sensor_value']) if pd.notna(row['avg_sensor_value']) else 0.0,
            float(row['min_sensor_value']) if pd.notna(row['min_sensor_value']) else 0.0,
            float(row['max_sensor_value']) if pd.notna(row['max_sensor_value']) else 0.0,
            float(row['usage_hours']) if pd.notna(row['usage_hours']) else 0.0,
            int(row['year']) if pd.notna(row['year']) else 0,
            int(row['month']) if pd.notna(row['month']) else 0,
            int(row['week']) if pd.notna(row['week']) else 0,
            int(row['day_of_week']) if pd.notna(row['day_of_week']) else 0,
            str(row['user_name']) if pd.notna(row['user_name']) else None,
            row['prosthesis_install_date'].date() if pd.notna(row.get('prosthesis_install_date')) else None,
            str(row['prosthesis_type']) if pd.notna(row.get('prosthesis_type')) else None,
            row['order_date'].date() if pd.notna(row.get('order_date')) else None,
            str(row['order_status']) if pd.notna(row.get('order_status')) else None,
            row['maintenance_date'].date() if pd.notna(row.get('maintenance_date')) else None,
            str(row['maintenance_type']) if pd.notna(row.get('maintenance_type')) else None,
            str(row['maintenance_status']) if pd.notna(row.get('maintenance_status')) else None,
            execution_date,
            execution_date - timedelta(days=1),
            execution_date,
        ))
    
    # Вставляем данные в ClickHouse
    insert_query = f"""
    INSERT INTO {DATA_MART_TABLE} VALUES
    """
    
    client.execute(insert_query, data_to_insert)
    
    print(f"Загружено {len(data_to_insert)} записей в ClickHouse таблицу {DATA_MART_TABLE}")
    
    # Проверяем количество записей в таблице
    count_query = f"SELECT count() FROM {DATA_MART_TABLE}"
    total_count = client.execute(count_query)[0][0]
    print(f"Всего записей в витрине: {total_count}")


# Определение задач DAG
extract_sensor_task = PythonOperator(
    task_id='extract_sensor_data',
    python_callable=extract_sensor_data,
    dag=dag,
)

extract_crm_task = PythonOperator(
    task_id='extract_crm_data',
    python_callable=extract_crm_data,
    dag=dag,
)

transform_task = PythonOperator(
    task_id='transform_and_aggregate',
    python_callable=transform_and_aggregate,
    dag=dag,
)

load_task = PythonOperator(
    task_id='load_to_clickhouse',
    python_callable=load_to_clickhouse,
    dag=dag,
)

# Определение зависимостей между задачами
[extract_sensor_task, extract_crm_task] >> transform_task >> load_task
