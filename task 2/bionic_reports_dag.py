from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.clickhouse.hooks.clickhouse import ClickHouseHook
import requests
import pandas as pd
from io import StringIO

default_args = {
    'owner': 'bionic',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2025, 1, 1),
}

dag = DAG(
    'bionic_daily_report_etl',
    default_args=default_args,
    description='ETL for user reports from CRM and telemetry',
    schedule_interval='0 2 * * *',  # ежедневно в 2:00
    catchup=False,
    tags=['bionic', 'reports'],
)

def extract_crm(**context):
    """Извлечение данных из CRM (Битрикс24) через REST API"""
    # Пример: получаем список пользователей с полями
    # В реальности нужно использовать OAuth и пагинацию
    crm_url = "https://bionic.bitrix24.ru/rest/1/user.get"
    params = {
        'auth': 'your_webhook_key',
        'FILTER': {'ACTIVE': 'Y'},
        'SELECT': ['ID', 'NAME', 'LAST_NAME', 'UF_PROSTHESIS_SN']
    }
    response = requests.get(crm_url, params=params)
    data = response.json()
    # Преобразуем в DataFrame
    users_df = pd.json_normalize(data['result'])
    # Сохраняем в XCom или временный файл
    context['ti'].xcom_push(key='crm_users', value=users_df.to_json())
    return 'CRM extracted'

def extract_telemetry(**context):
    """Извлечение телеметрии из PostgreSQL за вчерашний день"""
    pg_hook = PostgresHook(postgres_conn_id='bionic_postgres')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    sql = f"""
        SELECT user_id, timestamp, movement_type, response_time_ms, battery_voltage
        FROM telemetry
        WHERE DATE(timestamp) = '{yesterday}'
    """
    df = pg_hook.get_pandas_df(sql)
    context['ti'].xcom_push(key='telemetry_df', value=df.to_json())
    return 'Telemetry extracted'

def transform_and_load(**context):
    """Трансформация и загрузка в ClickHouse"""
    ti = context['ti']
    users_json = ti.xcom_pull(key='crm_users', task_ids='extract_crm')
    tele_json = ti.xcom_pull(key='telemetry_df', task_ids='extract_telemetry')

    users_df = pd.read_json(users_json)
    tele_df = pd.read_json(tele_json)

    # Агрегация телеметрии по пользователю и дате
    tele_df['report_date'] = pd.to_datetime(tele_df['timestamp']).dt.date
    agg = tele_df.groupby(['user_id', 'report_date']).agg(
        total_movements=('movement_type', 'count'),
        avg_response_ms=('response_time_ms', 'mean'),
        battery_drain_pct=('battery_voltage', lambda x: (x.max() - x.min()) / x.max() * 100),
        session_count=('timestamp', lambda x: x.diff().gt(pd.Timedelta(minutes=5)).cumsum().nunique())
    ).reset_index()

    # Присоединяем данные CRM (например, firmware_version из кастомного поля)
    # Допустим, что в CRM хранится серийный номер протеза, по которому можно получить версию прошивки
    # Для простоты оставим пока пустым
    agg['firmware_version'] = 'v2.1'

    # Загрузка в ClickHouse
    ch_hook = ClickHouseHook(clickhouse_conn_id='bionic_clickhouse')
    # Очистка за этот день (чтобы избежать дублей)
    ch_hook.run(f"ALTER TABLE bionic.user_daily_report DELETE WHERE report_date = '{agg['report_date'].iloc[0]}'")
    # Вставка через DataFrame
    ch_hook.insert_dataframe(table='bionic.user_daily_report', dataframe=agg)
    return 'Load completed'

with dag:
    t1 = PythonOperator(task_id='extract_crm', python_callable=extract_crm)
    t2 = PythonOperator(task_id='extract_telemetry', python_callable=extract_telemetry)
    t3 = PythonOperator(task_id='transform_and_load', python_callable=transform_and_load)

    [t1, t2] >> t3