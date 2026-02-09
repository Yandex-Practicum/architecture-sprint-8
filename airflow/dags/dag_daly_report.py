"""
device_report_dag.py
Рабочий DAG для Airflow 2.9.1
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from clickhouse_driver import Client as ClickHouseClient
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Конфигурация
CLICKHOUSE_CONFIG = {
    'host': 'clickhouse',
    'port': 9000,
    'user': 'default',
    'password': '',
    'database': 'reports',
}

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'catchup': False,
}

def extract_telemetry():
    """Извлечение телеметрии"""
    logger.info("Извлечение телеметрии")

    hook = PostgresHook(postgres_conn_id='pg_telemetry')

    # Вчерашняя дата
    yesterday = (datetime.now() - timedelta(days=1)).date()

    query = f"""
    SELECT 
        device_sn,
        MIN(response_speed) as min_speed,
        MAX(response_speed) as max_speed,
        AVG(response_speed) as avg_speed,
        MIN(battery_level) as min_battery,
        MAX(battery_level) as max_battery,
        COUNT(*) as total_signals,
        SUM(CASE WHEN error_code IS NOT NULL THEN 1 ELSE 0 END) as total_errors
    FROM device_telemetries
    WHERE DATE(started_at) = '{yesterday}'
    GROUP BY device_sn
    """

    df = hook.get_pandas_df(query)
    logger.info(f"Извлечено {len(df)} записей телеметрии")

    return df.to_dict('records'), yesterday

def extract_clients():
    """Извлечение клиентов"""
    logger.info("Извлечение клиентов")

    hook = PostgresHook(postgres_conn_id='pg_clients')

    query = """
    SELECT 
        client_id,
        client_name,
        device_sn,
        manufacturing_date
    FROM client_info
    WHERE device_sn IS NOT NULL
    """

    df = hook.get_pandas_df(query)
    logger.info(f"Извлечено {len(df)} клиентов")

    return df.to_dict('records')

def process_data(**context):
    """Обработка данных"""
    ti = context['ti']

    telemetry_data, report_date = ti.xcom_pull(task_ids='extract_telemetry')
    clients_data = ti.xcom_pull(task_ids='extract_clients')

    if not telemetry_data:
        logger.info("Нет данных телеметрии")
        return []

    # Создаем DataFrame
    telemetry_df = pd.DataFrame(telemetry_data)
    clients_df = pd.DataFrame(clients_data)

    # Создаем словарь для быстрого поиска клиентов
    device_to_client = {}
    if not clients_df.empty:
        device_to_client = clients_df.set_index('device_sn').to_dict('index')

    # Обрабатываем каждое устройство
    result = []
    for _, row in telemetry_df.iterrows():
        device_sn = row['device_sn']

        # Получаем данные клиента
        client_info = device_to_client.get(device_sn, {})
        client_id = client_info.get('client_id')
        client_name = client_info.get('client_name', 'Неизвестно')
        manufacturing_date = client_info.get('manufacturing_date')

        # Рассчитываем дни использования
        if manufacturing_date:
            manuf_date = pd.to_datetime(manufacturing_date).date()
            days_in_use = (report_date - manuf_date).days
        else:
            manuf_date = datetime(1970, 1, 1).date()
            days_in_use = 0

        result.append({
            'client_id': str(client_id),
            'client_name': str(client_name),
            'device_sn': str(device_sn),
            'min_response_speed': int(row['min_speed']),
            'max_response_speed': int(row['max_speed']),
            'avg_response_speed': int(round(row['avg_speed'])),
            'min_battery_level': float(row['min_battery']),
            'max_battery_level': float(row['max_battery']),
            'total_signals': int(row['total_signals']),
            'total_errors': int(row['total_errors']),
            'report_date': report_date,
            'manufacturing_date': manuf_date,
            'days_in_use': max(0, days_in_use)
        })

    logger.info(f"Обработано {len(result)} устройств")
    return result

def load_to_clickhouse(**context):
    """Загрузка в ClickHouse"""
    ti = context['ti']
    data = ti.xcom_pull(task_ids='process_data')

    if not data:
        logger.info("Нет данных для загрузки")
        return

    logger.info(f"Загрузка {len(data)} записей в ClickHouse")

    # Подключаемся к ClickHouse
    client = ClickHouseClient(
        host=CLICKHOUSE_CONFIG['host'],
        port=CLICKHOUSE_CONFIG['port'],
        user=CLICKHOUSE_CONFIG['user'],
        password=CLICKHOUSE_CONFIG['password'],
        database=CLICKHOUSE_CONFIG['database']
    )


    # Подготавливаем данные для вставки
    insert_data = []
    for record in data:
        insert_data.append((
            record['client_id'],
            record['client_name'],
            record['device_sn'],
            record['min_response_speed'],
            record['max_response_speed'],
            record['avg_response_speed'],
            record['min_battery_level'],
            record['max_battery_level'],
            record['total_signals'],
            record['total_errors'],
            record['report_date'],
            record['manufacturing_date'],
            record['days_in_use']
        ))

    # Вставляем данные
    insert_sql = """
    INSERT INTO device_daily_report 
    (client_id, client_name, device_sn, min_response_speed, max_response_speed, 
     avg_response_speed, min_battery_level, max_battery_level, total_signals, 
     total_errors, report_date, manufacturing_date, days_in_use)
    VALUES
    """

    client.execute(insert_sql, insert_data)

    logger.info(f"Успешно загружено {len(insert_data)} записей")

# Создаем DAG
with DAG(
        'device_daily_report',
        default_args=default_args,
        description='Ежедневный отчет по устройствам',
        schedule_interval='0 10 * * *',
        catchup=False,
        tags=['etl', 'report'],
) as dag:

    # Задачи
    extract_telemetry_task = PythonOperator(
        task_id='extract_telemetry',
        python_callable=extract_telemetry,
    )

    extract_clients_task = PythonOperator(
        task_id='extract_clients',
        python_callable=extract_clients,
    )

    process_data_task = PythonOperator(
        task_id='process_data',
        python_callable=process_data,
    )

    load_to_ch_task = PythonOperator(
        task_id='load_to_clickhouse',
        python_callable=load_to_clickhouse,
    )

    # Порядок выполнения
    [extract_telemetry_task, extract_clients_task] >> process_data_task >> load_to_ch_task