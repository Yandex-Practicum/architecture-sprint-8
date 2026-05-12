from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from clickhouse_driver import Client
import requests
import os

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
    schedule_interval="0 */6 * * *",  # 6 часов
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
    return resp.json()["access_token"]


def extract_users_from_keycloak(**context):
    """Загружает пользователей из Keycloak"""
    token = get_keycloak_token()
    url = "http://keycloak:8080/admin/realms/reports-realm/users"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    users = response.json()

    context["task_instance"].xcom_push(key="keycloak_users", value=users)
    return users


def load_users_to_clickhouse(**context):
    """Загружает пользователей в ClickHouse"""
    users = context["task_instance"].xcom_pull(key="keycloak_users")
    ch_client = Client(host="clickhouse", port=9000, database="reports")

    for user in users:
        # Определяем роль из realmRoles
        roles = user.get("realmRoles", [])
        if "prothetic_user" in roles:
            role = "prothetic_user"
        elif "administrator" in roles:
            role = "administrator"
        else:
            role = "user"

        sql = f"""
            INSERT INTO dim_users (user_id, email, full_name, role, region, created_at)
            VALUES ('{user["username"]}', '{user.get("email", "")}', 
                    '{user.get("firstName", "")} {user.get("lastName", "")}',
                    '{role}', 'RU', now())
        """
        ch_client.execute(sql)


def build_daily_stats_mart(**context):
    """Строит витрину daily_user_stats за вчерашний день"""
    ch_client = Client(host="clickhouse", port=9000, database="reports")

    sql = """
          INSERT INTO daily_user_stats
          SELECT t.user_id, \
                 t.prosthesis_id, \
                 toDate(t.timestamp) as date,
            count(*) as total_movements,
            avg(t.signal_quality) as avg_signal_quality,
            min(t.battery_level) as min_battery_level,
            countDistinct(t.calibration_id) as calibration_count,
            any(u.region) as region
          FROM raw_telemetry t
              LEFT JOIN dim_users u \
          ON t.user_id = u.user_id
          WHERE toDate(t.timestamp) = yesterday()
          GROUP BY t.user_id, t.prosthesis_id, date \
          """
    ch_client.execute(sql)


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
