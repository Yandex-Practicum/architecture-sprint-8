import logging
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

logger = logging.getLogger(__name__)

# ============================================================
# Параметры подключений
# ============================================================

CRM_CONN = {
    "host": "crm_db",
    "port": 5432,
    "dbname": "crm_db",
    "user": "crm_user",
    "password": "crm_password",
}

CLICKHOUSE_HTTP_URL = "http://olap_db:8123"


# ============================================================
# Функции ETL
# ============================================================


def extract_crm_customers(**kwargs):
    """Извлекает данные клиентов из CRM (PostgreSQL)."""
    import psycopg2

    conn = psycopg2.connect(**CRM_CONN)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, email, age, gender, country, address, phone FROM customers"
    )
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    cursor.close()
    conn.close()

    customers = [dict(zip(columns, row)) for row in rows]
    logger.info(f"Извлечено {len(customers)} клиентов из CRM")
    kwargs["ti"].xcom_push(key="customers", value=customers)


def load_customers_to_clickhouse(**kwargs):
    """Загружает данные клиентов из CRM в ClickHouse (OLAP)."""
    customers = kwargs["ti"].xcom_pull(
        task_ids="extract_crm_customers", key="customers"
    )

    # Создаём таблицу customers в ClickHouse, если ещё не существует
    create_table_query = """
        CREATE TABLE IF NOT EXISTS customers (
            id UInt32,
            name String,
            email String,
            age UInt16,
            gender String,
            country String,
            address String,
            phone String
        ) ENGINE = ReplacingMergeTree()
        ORDER BY id
    """
    requests.post(CLICKHOUSE_HTTP_URL, data=create_table_query)

    # Очищаем таблицу перед полной загрузкой (full refresh)
    requests.post(CLICKHOUSE_HTTP_URL, data="TRUNCATE TABLE IF EXISTS customers")

    # Вставляем данные батчами
    batch_size = 500
    for i in range(0, len(customers), batch_size):
        batch = customers[i: i + batch_size]
        values = []
        for c in batch:
            name = str(c["name"]).replace("'", "\\'")
            email = str(c["email"]).replace("'", "\\'")
            gender = str(c["gender"]).replace("'", "\\'")
            country = str(c["country"]).replace("'", "\\'")
            address = str(c["address"]).replace("'", "\\'")
            phone = str(c["phone"]).replace("'", "\\'")
            values.append(
                f"({c['id']}, '{name}', '{email}', "
                f"{c['age']}, '{gender}', '{country}', "
                f"'{address}', '{phone}')"
            )
        insert_query = (
                "INSERT INTO customers "
                "(id, name, email, age, gender, country, address, phone) VALUES "
                + ", ".join(values)
        )
        resp = requests.post(CLICKHOUSE_HTTP_URL, data=insert_query)
        if resp.status_code != 200:
            raise Exception(f"ClickHouse insert error: {resp.text}")

    logger.info(f"Загружено {len(customers)} клиентов в ClickHouse")


def create_customer_telemetry_datamart(**kwargs):
    """
    Создаёт витрину — объединяет данные телеметрии (emg_sensor_data)
    с данными клиентов (customers) из CRM. Группировка по клиентам
    для быстрого доступа к аналитике по пользователям.
    """

    # Создаём таблицу-витрину
    create_datamart_query = """
        CREATE TABLE IF NOT EXISTS customer_telemetry_datamart (
            customer_id UInt32,
            customer_name String,
            email String,
            age UInt16,
            gender String,
            country String,

            prosthesis_type String,
            muscle_group String,

            total_signals UInt64,
            avg_signal_frequency Float64,
            avg_signal_duration Float64,
            avg_signal_amplitude Float64,
            min_signal_amplitude Float64,
            max_signal_amplitude Float64,
            total_signal_duration UInt64,

            first_signal_time DateTime,
            last_signal_time DateTime,

            updated_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (customer_id, prosthesis_type, muscle_group)
    """
    resp = requests.post(CLICKHOUSE_HTTP_URL, data=create_datamart_query)
    if resp.status_code != 200:
        raise Exception(f"ClickHouse create datamart error: {resp.text}")

    # Очищаем витрину перед пересозданием
    requests.post(
        CLICKHOUSE_HTTP_URL,
        data="TRUNCATE TABLE IF EXISTS customer_telemetry_datamart",
    )

    # Заполняем витрину: JOIN телеметрии с клиентами, группировка по клиенту
    fill_datamart_query = """
        INSERT INTO customer_telemetry_datamart (
            customer_id,
            customer_name,
            email,
            age,
            gender,
            country,
            prosthesis_type,
            muscle_group,
            total_signals,
            avg_signal_frequency,
            avg_signal_duration,
            avg_signal_amplitude,
            min_signal_amplitude,
            max_signal_amplitude,
            total_signal_duration,
            first_signal_time,
            last_signal_time
        )
        SELECT
            c.id AS customer_id,
            c.name AS customer_name,
            c.email AS email,
            c.age AS age,
            c.gender AS gender,
            c.country AS country,
            t.prosthesis_type,
            t.muscle_group,
            count(*) AS total_signals,
            round(avg(t.signal_frequency), 2) AS avg_signal_frequency,
            round(avg(t.signal_duration), 2) AS avg_signal_duration,
            round(avg(t.signal_amplitude), 2) AS avg_signal_amplitude,
            min(t.signal_amplitude) AS min_signal_amplitude,
            max(t.signal_amplitude) AS max_signal_amplitude,
            sum(t.signal_duration) AS total_signal_duration,
            min(t.signal_time) AS first_signal_time,
            max(t.signal_time) AS last_signal_time
        FROM emg_sensor_data AS t
        INNER JOIN customers AS c ON t.user_id = c.id
        GROUP BY
            c.id,
            c.name,
            c.email,
            c.age,
            c.gender,
            c.country,
            t.prosthesis_type,
            t.muscle_group
    """
    resp = requests.post(CLICKHOUSE_HTTP_URL, data=fill_datamart_query)
    if resp.status_code != 200:
        raise Exception(f"ClickHouse fill datamart error: {resp.text}")

    # Проверяем количество записей
    count_resp = requests.post(
        CLICKHOUSE_HTTP_URL,
        data="SELECT count() FROM customer_telemetry_datamart",
    )
    logger.info(f"Витрина заполнена: {count_resp.text.strip()} строк")


# ============================================================
# Определение DAG
# ============================================================

default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
        dag_id="bionicpro_crm_to_olap_etl",
        default_args=default_args,
        description="ETL: CRM (PostgreSQL) → OLAP (ClickHouse) + витрина телеметрии",
        schedule_interval="0 2 * * *",  # каждый день в 02:00 UTC
        start_date=datetime(2025, 1, 1),
        catchup=False,
        tags=["bionicpro", "etl", "crm", "olap"],
) as dag:
    task_extract = PythonOperator(
        task_id="extract_crm_customers",
        python_callable=extract_crm_customers,
    )

    task_load = PythonOperator(
        task_id="load_customers_to_clickhouse",
        python_callable=load_customers_to_clickhouse,
    )

    task_datamart = PythonOperator(
        task_id="create_customer_telemetry_datamart",
        python_callable=create_customer_telemetry_datamart,
    )

    # Последовательность: извлечь → загрузить → построить витрину
    task_extract >> task_load >> task_datamart
