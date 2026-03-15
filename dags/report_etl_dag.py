"""
DAG для ETL процесса подготовки витрины отчётов
- Извлекает данные из CRM и телеметрии
- Трансформирует и аггрегирует
- Загружает в ClickHouse (через HTTP API)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import pandas as pd
import requests
import json
import logging

default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
}

dag = DAG(
    'bionicpro_report_etl',
    default_args=default_args,
    description='ETL process for report mart',
    schedule_interval='0 1 * * *',  # Каждый день в 01:00
    catchup=False,
    tags=['bionicpro', 'reports'],
)

# Конфигурация ClickHouse
CLICKHOUSE_HOST = 'clickhouse'  # или localhost для локальной разработки
CLICKHOUSE_PORT = '8123'
CLICKHOUSE_DB = 'reports'

def extract_crm_data(**context):
    """Извлечение данных из CRM (PostgreSQL)"""
    try:
        pg_hook = PostgresHook(postgres_conn_id='crm_postgres')

        # Забираем данные за последние сутки
        sql = """
        SELECT 
            u.id as user_id,
            u.username,
            u.email,
            u.first_name,
            u.last_name,
            p.id as prosthetic_id,
            p.model,
            p.installation_date,
            p.last_calibration
        FROM users u
        JOIN prosthetics p ON u.id = p.user_id
        WHERE p.last_calibration >= %s OR p.last_calibration IS NOT NULL
        """

        yesterday = (context['execution_date'] - timedelta(days=1)).date()
        df = pg_hook.get_pandas_df(sql, parameters=[yesterday])

        # Сохраняем в XCom для передачи в следующий таск
        if not df.empty:
            context['task_instance'].xcom_push(key='crm_data', value=df.to_json())
            logging.info(f"Extracted {len(df)} records from CRM")
        else:
            logging.info("No CRM data extracted")
            context['task_instance'].xcom_push(key='crm_data', value=None)

    except Exception as e:
        logging.error(f"Error extracting CRM data: {e}")
        # Не прерываем DAG, если нет данных из CRM
        context['task_instance'].xcom_push(key='crm_data', value=None)

def extract_telemetry_data(**context):
    """Извлечение данных телеметрии из PostgreSQL"""
    try:
        pg_hook = PostgresHook(postgres_conn_id='telemetry_postgres')

        # Проверяем, существует ли таблица
        check_sql = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'telemetry'
        );
        """
        exists = pg_hook.get_first(check_sql)[0]

        if not exists:
            logging.warning("Telemetry table does not exist")
            context['task_instance'].xcom_push(key='telemetry_data', value=None)
            return

        # Аггрегируем телеметрию по пользователям за сутки
        sql = """
        SELECT 
            t.user_id,
            DATE(t.timestamp) as report_date,
            COUNT(*) as movements_count,
            SUM(CASE WHEN t.success = true THEN 1 ELSE 0 END) as successful_movements,
            SUM(CASE WHEN t.success = false THEN 1 ELSE 0 END) as failed_movements,
            AVG(t.response_time) as avg_response_time_ms,
            SUM(t.battery_drain) as total_battery_drain,
            COUNT(DISTINCT t.calibration_id) as calibration_count,
            SUM(t.data_volume) as data_volume_mb
        FROM telemetry t
        WHERE DATE(t.timestamp) = %s
        GROUP BY t.user_id, DATE(t.timestamp)
        """

        yesterday = (context['execution_date'] - timedelta(days=1)).date()
        df = pg_hook.get_pandas_df(sql, parameters=[yesterday])

        if not df.empty:
            context['task_instance'].xcom_push(key='telemetry_data', value=df.to_json())
            logging.info(f"Extracted {len(df)} aggregated telemetry records")
        else:
            logging.info("No telemetry data for yesterday")
            context['task_instance'].xcom_push(key='telemetry_data', value=None)

    except Exception as e:
        logging.error(f"Error extracting telemetry data: {e}")
        context['task_instance'].xcom_push(key='telemetry_data', value=None)

def transform_and_join(**context):
    """Трансформация и объединение данных"""
    try:
        # Получаем данные из XCom
        ti = context['task_instance']
        crm_json = ti.xcom_pull(key='crm_data', task_ids='extract_crm_data')
        telemetry_json = ti.xcom_pull(key='telemetry_data', task_ids='extract_telemetry_data')

        # Если нет данных, выходим
        if not telemetry_json and not crm_json:
            logging.info("No data to process")
            context['task_instance'].xcom_push(key='report_data', value=None)
            return

        crm_df = pd.read_json(crm_json) if crm_json else pd.DataFrame()
        telemetry_df = pd.read_json(telemetry_json) if telemetry_json else pd.DataFrame()

        result_df = pd.DataFrame()

        if not telemetry_df.empty:
            # Если есть телеметрия, используем её как основу
            result_df = telemetry_df.copy()

            if not crm_df.empty:
                # Объединяем с CRM данными
                result_df = pd.merge(
                    result_df,
                    crm_df[['user_id', 'prosthetic_id']],
                    on='user_id',
                    how='left'
                )
            else:
                # Если нет CRM, заполняем заглушками
                result_df['prosthetic_id'] = 'unknown'

            # Добавляем вычисляемые поля
            result_df['total_usage_minutes'] = result_df['movements_count'] * 0.5
            result_df['battery_cycles'] = (result_df['total_battery_drain'] / 100).fillna(0).astype(int)

            # Выбираем нужные колонки
            result_df = result_df[[
                'user_id', 'report_date', 'prosthetic_id', 'total_usage_minutes',
                'avg_response_time_ms', 'battery_cycles', 'movements_count',
                'successful_movements', 'failed_movements', 'calibration_count',
                'data_volume_mb'
            ]]
        else:
            logging.info("No telemetry data to transform")

        if not result_df.empty:
            context['task_instance'].xcom_push(key='report_data', value=result_df.to_json())
            logging.info(f"Transformed {len(result_df)} records for report mart")
        else:
            context['task_instance'].xcom_push(key='report_data', value=None)
            logging.info("No transformed data to process")

    except Exception as e:
        logging.error(f"Error transforming data: {e}")
        context['task_instance'].xcom_push(key='report_data', value=None)
        raise

def load_to_clickhouse(**context):
    """Загрузка данных в ClickHouse через HTTP API"""
    try:
        ti = context['task_instance']
        data_json = ti.xcom_pull(key='report_data', task_ids='transform_and_join')

        if not data_json:
            logging.info("No data to load to ClickHouse")
            return

        df = pd.read_json(data_json)

        if df.empty:
            logging.info("Empty dataframe, nothing to load")
            return

        # Создаем таблицу, если не существует
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS reports.report_fact (
            user_id String,
            report_date Date,
            prosthetic_id String,
            total_usage_minutes Float32,
            avg_response_time_ms Float32,
            battery_cycles UInt16,
            movements_count UInt32,
            successful_movements UInt32,
            failed_movements UInt32,
            calibration_count UInt16,
            data_volume_mb Float32,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(report_date)
        ORDER BY (user_id, report_date);
        """

        # Выполняем через HTTP API
        create_response = requests.post(
            f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}",
            params={"database": CLICKHOUSE_DB, "query": create_table_sql}
        )
        create_response.raise_for_status()

        # Вставляем данные
        for _, row in df.iterrows():
            insert_sql = f"""
            INSERT INTO reports.report_fact (
                user_id, report_date, prosthetic_id, total_usage_minutes,
                avg_response_time_ms, battery_cycles, movements_count,
                successful_movements, failed_movements, calibration_count,
                data_volume_mb
            ) VALUES (
                {row['user_id']}', 
                {row['report_date']}', 
                {row['prosthetic_id']}', 
                {row['total_usage_minutes']},
                {row['avg_response_time_ms']}, 
                {row['battery_cycles']}, 
                {row['movements_count']},
                {row['successful_movements']}, 
                {row['failed_movements']}, 
                {row['calibration_count']},
                {row['data_volume_mb']}
            )
            """

            response = requests.post(
                f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}",
                params={"database": CLICKHOUSE_DB, "query": insert_sql}
            )
            response.raise_for_status()

        logging.info(f"Loaded {len(df)} records to ClickHouse")

    except Exception as e:
        logging.error(f"Error loading to ClickHouse: {e}")
        raise

# Определяем задачи
extract_crm = PythonOperator(
    task_id='extract_crm_data',
    python_callable=extract_crm_data,
    dag=dag,
)

extract_telemetry = PythonOperator(
    task_id='extract_telemetry_data',
    python_callable=extract_telemetry_data,
    dag=dag,
)

transform = PythonOperator(
    task_id='transform_and_join',
    python_callable=transform_and_join,
    dag=dag,
)

load = PythonOperator(
    task_id='load_to_clickhouse',
    python_callable=load_to_clickhouse,
    dag=dag,
)

# Определяем порядок выполнения
[extract_crm, extract_telemetry] >> transform >> load