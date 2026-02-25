import logging
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

logger = logging.getLogger(__name__)

# ============================================================
# Connection parameters
# ============================================================

CRM_CONN = {
    "host": "crm_db",
    "port": 5432,
    "dbname": "crm_db",
    "user": "crm_user",
    "password": "crm_password",
}

CLICKHOUSE_HTTP_URL = "http://olap_db:8123"

# S3 (Minio) connection parameters for cache invalidation
S3_ENDPOINT_URL = "http://minio:9000"
S3_ACCESS_KEY = "minio_user"
S3_SECRET_KEY = "minio_password"
S3_BUCKET_NAME = "bionicpro-reports"


# ============================================================
# ETL Functions
# ============================================================


def extract_crm_customers(**kwargs):
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
    logger.info(f"Extracted {len(customers)} customers from CRM")
    kwargs["ti"].xcom_push(key="customers", value=customers)


def load_customers_to_clickhouse(**kwargs):
    customers = kwargs["ti"].xcom_pull(
        task_ids="extract_crm_customers", key="customers"
    )

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

    requests.post(CLICKHOUSE_HTTP_URL, data="TRUNCATE TABLE IF EXISTS customers")

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

    logger.info(f"Loaded {len(customers)} customers to ClickHouse")


def create_customer_telemetry_datamart(**kwargs):
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

    requests.post(
        CLICKHOUSE_HTTP_URL,
        data="TRUNCATE TABLE IF EXISTS customer_telemetry_datamart",
    )

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

    count_resp = requests.post(
        CLICKHOUSE_HTTP_URL,
        data="SELECT count() FROM customer_telemetry_datamart",
    )
    logger.info(f"Datamart filled: {count_resp.text.strip()} rows")


def invalidate_s3_report_cache(**kwargs):
    """
    Invalidate S3 report cache after ETL datamart update.

    Cache update mechanism:
    1. Primary: versioning by datamart_updated_at — new reports automatically
       get a different URL (version hash), so old CDN cache doesn't interfere.
    2. Additional: this function deletes old reports from S3 to free storage.
    3. CDN (Nginx) cache is invalidated automatically via proxy_cache_valid TTL
       or through URL change.
    """
    import boto3
    from botocore.exceptions import ClientError

    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name='us-east-1',
        )

        prefix = "reports/"
        deleted_count = 0

        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=prefix):
                objects = page.get('Contents', [])
                if objects:
                    delete_keys = [{'Key': obj['Key']} for obj in objects]
                    s3_client.delete_objects(
                        Bucket=S3_BUCKET_NAME,
                        Delete={'Objects': delete_keys}
                    )
                    deleted_count += len(delete_keys)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucket':
                logger.info(f"Bucket '{S3_BUCKET_NAME}' does not exist yet, skipping")
                return
            raise

        logger.info(f"S3 cache invalidation complete: deleted {deleted_count} old reports")

    except Exception as e:
        logger.warning(f"S3 cache invalidation failed (non-critical): {str(e)}")


# ============================================================
# DAG Definition
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
        description="ETL: CRM (PostgreSQL) -> OLAP (ClickHouse) + datamart + S3 cache invalidation",
        schedule_interval="0 2 * * *",
        start_date=datetime(2025, 1, 1),
        catchup=False,
        tags=["bionicpro", "etl", "crm", "olap", "cache"],
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

    task_invalidate_cache = PythonOperator(
        task_id="invalidate_s3_report_cache",
        python_callable=invalidate_s3_report_cache,
    )

    # Sequence: extract -> load -> build datamart -> invalidate cache
    task_extract >> task_load >> task_datamart >> task_invalidate_cache
