from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import requests
import os
import logging
from clickhouse_driver import Client

default_args = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "reports_etl",
    default_args=default_args,
    description="ETL: Keycloak users + telemetry → ClickHouse",
    schedule_interval="0 */6 * * *",
    catchup=False,
    tags=["reports", "bionicpro"],
)


def get_keycloak_token():
    """Получение admin-токена Keycloak"""
    url = "http://keycloak:8080/realms/master/protocol/openid-connect/token"
    data = {
        "client_id": "admin-cli",
        "username": os.getenv("KEYCLOAK_ADMIN", "admin"),
        "password": os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin"),
        "grant_type": "password"
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]


def extract_users_from_keycloak(**context):
    """Загружает пользователей из Keycloak"""
    try:
        token = get_keycloak_token()
        url = "http://keycloak:8080/admin/realms/reports-realm/users"
        headers = {"Authorization": f"Bearer {token}"}

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        users = response.json()

        context["task_instance"].xcom_push(key="keycloak_users", value=users)
        logging.info(f"Extracted {len(users)} users from Keycloak")
        return users
    except Exception as e:
        logging.error(f"Error extracting users: {e}")
        raise


def load_users_to_clickhouse(**context):
    """Загружает пользователей в ClickHouse"""
    try:
        users = context["task_instance"].xcom_pull(key="keycloak_users")
        ch_client = Client(host="clickhouse", port=9000, database="reports")

        inserted = 0
        for user in users:
            # Определяем роль из realmRoles
            roles = user.get("realmRoles", [])
            if "prothetic_user" in roles:
                role = "prothetic_user"
            elif "administrator" in roles:
                role = "administrator"
            else:
                role = "user"

            sql = """
                  INSERT INTO dim_users (user_id, email, full_name, role, region, created_at)
                  VALUES (%(user_id)s, %(email)s, %(full_name)s, %(role)s, %(region)s, now()) \
                  """

            full_name = f"{user.get('firstName', '')} {user.get('lastName', '')}".strip()

            ch_client.execute(sql, {
                "user_id": user["username"],
                "email": user.get("email", ""),
                "full_name": full_name,
                "role": role,
                "region": "RU"
            })
            inserted += 1

        logging.info(f"Loaded {inserted} users to ClickHouse")
    except Exception as e:
        logging.error(f"Error loading users: {e}")
        raise


def build_daily_stats_mart(**context):
    """Строит витрину daily_user_stats за вчерашний день"""
    try:
        ch_client = Client(host="clickhouse", port=9000, database="reports")

        # Исправленный SQL запрос
        sql = """
              INSERT INTO daily_user_stats
              SELECT t.user_id, \
                     t.prosthesis_id, \
                     toDate(t.timestamp) as date,
                count(*) as total_movements,
                avg(t.signal_quality) as avg_signal_quality,
                min(t.battery_level) as min_battery_level,
                count(DISTINCT t.calibration_id) as calibration_count,
                any(u.region) as region
              FROM raw_telemetry t
                  LEFT JOIN dim_users u \
              ON t.user_id = u.user_id
              WHERE toDate(t.timestamp) = yesterday()
              GROUP BY t.user_id, t.prosthesis_id, date \
              """
        ch_client.execute(sql)
        logging.info("Daily stats mart built successfully")
    except Exception as e:
        logging.error(f"Error building stats mart: {e}")
        raise


# Tasks
extract_users = PythonOperator(
    task_id="extract_users_from_keycloak",
    python_callable=extract_users_from_keycloak,
    dag=dag,
)

load_users = PythonOperator(
    task_id="load_users_to_clickhouse",
    python_callable=load_users_to_clickhouse,
    dag=dag,
)

build_mart = PythonOperator(
    task_id="build_daily_stats_mart",
    python_callable=build_daily_stats_mart,
    dag=dag,
)

extract_users >> load_users >> build_mart
