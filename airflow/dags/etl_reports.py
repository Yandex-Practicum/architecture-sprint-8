"""
ETL DAG: Extract data from CRM DB (PostgreSQL) and load into ClickHouse OLAP.

This DAG:
1. Extracts customer data from CRM
2. Extracts order data from CRM
3. Extracts telemetry data from CRM
4. Transforms and loads into ClickHouse reports table
5. Refreshes the report_datamart
"""

import os
from datetime import datetime, date, timedelta

import psycopg2
import clickhouse_connect

from airflow import DAG
from airflow.operators.python import PythonOperator


def _serialize_rows(rows):
    """Convert datetime/date objects in rows to ISO strings for XCom JSON serialization."""
    result = []
    for row in rows:
        serialized = []
        for val in row:
            if isinstance(val, datetime):
                serialized.append(val.isoformat())
            elif isinstance(val, date):
                serialized.append(val.isoformat())
            else:
                serialized.append(val)
        result.append(serialized)
    return result

# CRM DB connection settings (from environment)
CRM_DB_CONFIG = {
    "host": os.getenv("CRM_DB_HOST", "crm-db"),
    "port": int(os.getenv("CRM_DB_PORT", "5432")),
    "dbname": os.getenv("CRM_DB_NAME", "crm"),
    "user": os.getenv("CRM_DB_USER", "crm_user"),
    "password": os.getenv("CRM_DB_PASSWORD", "crm_password"),
}

# ClickHouse connection settings
CH_CONFIG = {
    "host": os.getenv("CLICKHOUSE_HOST", "clickhouse"),
    "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
    "database": os.getenv("CLICKHOUSE_DB", "bionicpro"),
}


def get_crm_connection():
    return psycopg2.connect(**CRM_DB_CONFIG)


def get_ch_client():
    return clickhouse_connect.get_client(**CH_CONFIG)


def extract_customers(**kwargs):
    """Extract customer data from CRM PostgreSQL."""
    conn = get_crm_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, keycloak_user_id, email, first_name, last_name, created_at FROM customers"
        )
        rows = cur.fetchall()
        kwargs["ti"].xcom_push(key="customers", value=_serialize_rows(rows))
        return len(rows)
    finally:
        conn.close()


def extract_orders(**kwargs):
    """Extract order data from CRM PostgreSQL."""
    conn = get_crm_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, customer_id, product_name, product_type, order_date, status, created_at FROM orders"
        )
        rows = cur.fetchall()
        kwargs["ti"].xcom_push(key="orders", value=_serialize_rows(rows))
        return len(rows)
    finally:
        conn.close()


def extract_telemetry(**kwargs):
    """Extract telemetry data from CRM PostgreSQL."""
    conn = get_crm_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, device_id, customer_id, signal_strength, usage_hours,
                      active_movements, battery_cycles, error_count, recorded_at
               FROM telemetry"""
        )
        rows = cur.fetchall()
        kwargs["ti"].xcom_push(key="telemetry", value=_serialize_rows(rows))
        return len(rows)
    finally:
        conn.close()


def transform_and_load(**kwargs):
    """Join CRM + telemetry data and load into ClickHouse reports table."""
    ti = kwargs["ti"]
    customers = ti.xcom_pull(key="customers", task_ids="extract_customers")
    orders = ti.xcom_pull(key="orders", task_ids="extract_orders")
    telemetry = ti.xcom_pull(key="telemetry", task_ids="extract_telemetry")

    if not customers or not orders or not telemetry:
        print("No data to process")
        return 0

    # Build lookup: customer_id -> customer info
    customer_map = {}
    for row in customers:
        cid, kc_user_id, email, first_name, last_name, created_at = row
        customer_map[cid] = {
            "keycloak_user_id": kc_user_id,
            "email": email,
        }

    # Build lookup: customer_id -> orders
    order_map = {}
    for row in orders:
        oid, cust_id, product_name, product_type, order_date, status, created_at = row
        if cust_id not in order_map:
            order_map[cust_id] = []
        order_map[cust_id].append({
            "product_name": product_name,
            "order_date": order_date,
            "status": status,
        })

    # Aggregate telemetry by customer_id + device_id + date
    from collections import defaultdict

    agg = defaultdict(lambda: {
        "usage_hours": 0.0,
        "active_movements": 0,
        "battery_cycles": 0,
        "signal_strengths": [],
        "error_count": 0,
    })

    for row in telemetry:
        tid, device_id, cust_id, sig, hours, movements, battery, errors, recorded_at = row
        # recorded_at is an ISO string after serialization; extract date part
        recorded_date = recorded_at[:10] if isinstance(recorded_at, str) else str(recorded_at)
        key = (cust_id, device_id, str(recorded_date))
        agg[key]["usage_hours"] += hours or 0
        agg[key]["active_movements"] += movements or 0
        agg[key]["battery_cycles"] += battery or 0
        agg[key]["error_count"] += errors or 0
        if sig:
            agg[key]["signal_strengths"].append(sig)

    # Build report rows
    report_rows = []
    for (cust_id, device_id, date_str), metrics in agg.items():
        cust = customer_map.get(cust_id, {})
        if not cust:
            continue

        # Find matching order for this customer
        cust_orders = order_map.get(cust_id, [])
        product_name = cust_orders[0]["product_name"] if cust_orders else "Unknown"
        order_date_str = cust_orders[0]["order_date"] if cust_orders else date_str
        order_status = cust_orders[0]["status"] if cust_orders else "unknown"

        avg_signal = (
            sum(metrics["signal_strengths"]) / len(metrics["signal_strengths"])
            if metrics["signal_strengths"]
            else 0.0
        )

        # Convert date strings to date objects for ClickHouse Date columns
        report_date_obj = date.fromisoformat(date_str)
        order_date_obj = date.fromisoformat(str(order_date_str))

        report_rows.append([
            cust["keycloak_user_id"],
            cust["email"],
            report_date_obj,
            device_id,
            product_name,
            order_date_obj,
            order_status,
            metrics["usage_hours"],
            metrics["active_movements"],
            metrics["battery_cycles"],
            avg_signal,
            metrics["error_count"],
        ])

    if not report_rows:
        print("No report rows generated")
        return 0

    # Load into ClickHouse
    ch = get_ch_client()

    # Clear existing data and reload (full refresh strategy)
    ch.command("TRUNCATE TABLE IF EXISTS bionicpro.reports")

    ch.insert(
        "bionicpro.reports",
        report_rows,
        column_names=[
            "user_id", "user_email", "report_date", "device_id",
            "product_name", "order_date", "order_status",
            "total_usage_hours", "active_movements", "battery_cycles",
            "avg_signal_strength", "error_count",
        ],
    )

    # Also refresh the report_datamart
    ch.command("TRUNCATE TABLE IF EXISTS bionicpro.report_datamart")
    ch.command("""
        INSERT INTO bionicpro.report_datamart
        SELECT
            user_id,
            user_email,
            device_id,
            product_name,
            report_date AS order_date,
            order_status,
            sum(total_usage_hours) AS total_usage_hours,
            sum(active_movements) AS total_active_movements,
            sum(battery_cycles) AS total_battery_cycles,
            avg(avg_signal_strength) AS avg_signal_strength,
            sum(error_count) AS total_error_count,
            now() AS last_updated
        FROM bionicpro.reports
        GROUP BY user_id, user_email, device_id, product_name, report_date, order_status
    """)

    # Record ETL run metadata
    ch.command(f"""
        INSERT INTO bionicpro.etl_metadata VALUES
        ('etl_reports', now(), 'success', {len(report_rows)})
    """)

    print(f"Loaded {len(report_rows)} report rows into ClickHouse")
    return len(report_rows)


# DAG definition
default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "etl_reports",
    default_args=default_args,
    description="ETL: CRM DB + Telemetry -> ClickHouse reports data mart",
    schedule_interval="@daily",
    catchup=False,
    tags=["bionicpro", "etl", "reports"],
) as dag:

    t_extract_customers = PythonOperator(
        task_id="extract_customers",
        python_callable=extract_customers,
    )

    t_extract_orders = PythonOperator(
        task_id="extract_orders",
        python_callable=extract_orders,
    )

    t_extract_telemetry = PythonOperator(
        task_id="extract_telemetry",
        python_callable=extract_telemetry,
    )

    t_transform_load = PythonOperator(
        task_id="transform_and_load",
        python_callable=transform_and_load,
    )

    [t_extract_customers, t_extract_orders, t_extract_telemetry] >> t_transform_load
