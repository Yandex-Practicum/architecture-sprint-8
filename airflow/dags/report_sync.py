from __future__ import annotations
import time
import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
import clickhouse_connect
from sqlalchemy import create_engine, text 

PG_CONN = "postgresql://keycloak_user:keycloak_password@keycloak_db:5432/keycloak_db"
CH_HOST = "clickhouse"


CREATE_TELEMETRY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS telemetry (
    user_id VARCHAR(255),
    movement_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    battery_level DECIMAL(5, 2)
    );
    """
CREATE_CRM_CUSTOMERS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS crm_customers (
        user_id VARCHAR(255) PRIMARY KEY,
        first_name VARCHAR(255),
        last_name VARCHAR(255)
    );
    """

def create_pg_tables():
    """
    Создает таблицы telemetry и crm_customers в PostgreSQL.
    """
    engine = create_engine(PG_CONN)
    with engine.begin() as connection:
        connection.execute(text(CREATE_TELEMETRY_TABLE_SQL))
        connection.execute(text(CREATE_CRM_CUSTOMERS_TABLE_SQL))
    print("Таблицы PostgreSQL проверены/созданы")

def sync_data():
    try:
        engine = create_engine(PG_CONN)
        #данные из Postgres
        query = """
        SELECT
            t.user_id,
            COALESCE(c.first_name, 'Unknown') || ' ' || COALESCE(c.last_name, '') as full_name,
            COUNT(t.movement_id) as total_movements,
            AVG(t.battery_level) as avg_battery,
            MAX(t.timestamp) as last_activity
        FROM telemetry t
        JOIN crm_customers c ON t.user_id = c.user_id
        GROUP BY t.user_id, c.first_name, c.last_name
        """
        df = pd.read_sql(query, engine)
        
        if df.empty:
            print("Postgres is empty.")
            return

        #соед с ClickHouse
        client = clickhouse_connect.get_client(
            host=CH_HOST, port=8123, username='default', password='password123'
        )

        client.command("DROP TABLE IF EXISTS prothetic_reports")
        client.command("""
            CREATE TABLE prothetic_reports (
                user_id String,
                full_name String,
                total_movements String,
                avg_battery String,
                last_activity String
            ) ENGINE = MergeTree() ORDER BY user_id
        """)
        for _, row in df.iterrows():
            user_id = str(row['user_id'])
            name = str(row['full_name']).replace("'", "")
            total = str(int(row['total_movements']))
            avg = str(round(float(row['avg_battery']), 2))
            last = str(row['last_activity'])[:19]

            sql = f"INSERT INTO prothetic_reports VALUES ('{user_id}', '{name}', '{total}', '{avg}', '{last}')"
            print(f"Executing: {sql}")
            client.command(sql)
        
        print(f"Successfully inserted {len(df)} rows via Raw SQL.")

    except Exception as e:
        print(f"Error: {e}")
        raise e


# DAG 
with DAG(
    dag_id='report_sync',
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule='@daily',
    catchup=False,
    tags=["bionicpro", "reports", "etl"],
) as dag:

    create_pg_tables_task = PythonOperator(
        task_id='create_pg_tables_if_not_exists',
        python_callable=create_pg_tables,
    )
    sync_task = PythonOperator(
        task_id='sync_crm_and_telemetry',
        python_callable=sync_data,
    )
    create_pg_tables_task >> sync_task