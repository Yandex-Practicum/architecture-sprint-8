from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Tuple

from airflow.decorators import dag, task
from clickhouse_driver import Client
import psycopg2

CRM_CONNECTION = {
    "host": "crm_db",
    "port": 5432,
    "dbname": "crm_db",
    "user": "crm_user",
    "password": "crm_password",
}

CLICKHOUSE_CONNECTION = {
    "host": "olap_db",
    "port": 9000,
    "user": "demo",
    "password": "demo",
    "secure": False,
}


@dag(
    dag_id="crm_to_olap_reporting",
    description=(
        "ETL CRM customers into ClickHouse and build telemetry reporting "
        "mart joined with customer profiles"
    ),
    schedule="0 * * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["etl", "crm", "clickhouse", "reporting"],
)
def crm_to_olap_reporting():
    @task()
    def fetch_customers() -> List[Tuple[int, str, str, float, str, str, str, str]]:
        with psycopg2.connect(**CRM_CONNECTION) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
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
                )
                rows = cursor.fetchall()

        sanitized_rows: List[Tuple[int, str, str, float, str, str, str, str]] = []
        for row in rows:
            (
                customer_id,
                name,
                email,
                age,
                gender,
                country,
                address,
                phone,
            ) = row
            sanitized_rows.append(
                (
                    int(customer_id),
                    name or "",
                    email or "",
                    float(age) if age is not None else 0.0,
                    gender or "unknown",
                    country or "",
                    address or "",
                    phone or "",
                )
            )

        return sanitized_rows

    @task()
    def load_customers(customers: List[Tuple[int, str, str, float, str, str, str, str]]):
        client = Client(**CLICKHOUSE_CONNECTION)
        client.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_customers (
                id UInt32,
                name String,
                email String,
                age Float32,
                gender String,
                country String,
                address String,
                phone String
            )
            ENGINE = ReplacingMergeTree()
            ORDER BY id
            """
        )
        client.execute("TRUNCATE TABLE crm_customers")

        if customers:
            client.execute(
                "INSERT INTO crm_customers (id, name, email, age, gender, country, address, phone) VALUES",
                customers,
            )

    @task()
    def build_reporting_table():
        client = Client(**CLICKHOUSE_CONNECTION)
        client.execute(
            """
            CREATE TABLE IF NOT EXISTS reporting_customer_telemetry (
                user_id UInt32,
                name String,
                email String,
                country String,
                age Float32,
                gender String,
                signals_total UInt64,
                prosthesis_types UInt64,
                avg_signal_amplitude Nullable(Decimal(10,4)),
                avg_signal_duration Nullable(Float64),
                first_signal_time Nullable(DateTime),
                last_signal_time Nullable(DateTime)
            )
            ENGINE = ReplacingMergeTree()
            ORDER BY user_id
            """
        )

        client.execute("TRUNCATE TABLE reporting_customer_telemetry")

        client.execute(
            """
            INSERT INTO reporting_customer_telemetry
            SELECT
                c.id AS user_id,
                c.name,
                c.email,
                c.country,
                c.age,
                c.gender,
                count(e.signal_time) AS signals_total,
                countDistinct(e.prosthesis_type) AS prosthesis_types,
                avgOrNull(e.signal_amplitude) AS avg_signal_amplitude,
                avgOrNull(e.signal_duration) AS avg_signal_duration,
                minOrNull(e.signal_time) AS first_signal_time,
                maxOrNull(e.signal_time) AS last_signal_time
            FROM crm_customers AS c
            LEFT JOIN emg_sensor_data AS e
            ON e.user_id = c.id
            GROUP BY
                c.id,
                c.name,
                c.email,
                c.country,
                c.age,
                c.gender
            """
        )

    customer_records = fetch_customers()
    loaded_customers = load_customers(customer_records)
    loaded_customers >> build_reporting_table()


crm_to_olap_reporting()