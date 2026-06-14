"""
BionicPRO Reports CDC ETL DAG

ETL-процесс для объединения данных телеметрии с CDC данными CRM из ClickHouse.
CRM данные поступают через CDC (Debezium → Kafka → ClickHouse).

DAG: bionicpro_reports_cdc_etl
Расписание: каждые 15 минут (*/15 * * * *)

ВАЖНО: Этот DAG заменяет bionicpro_reports_etl после внедрения CDC.
- CRM данные больше не извлекаются напрямую из PostgreSQL
- CRM данные читаются из ClickHouse (таблица cdc_customer_data)
- Телеметрия по-прежнему извлекается из Telemetry PostgreSQL
- Результат объединяется в витрину user_prosthesis_stats

Задание 4: Повышение оперативности и стабильности работы CRM
- CDC снимает нагрузку с CRM PostgreSQL
- OLTP операции не блокируются выгрузками
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import Variable
from airflow.utils.dates import days_ago

import pandas as pd
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

# ============================================================================
# Конфигурация DAG
# ============================================================================
DAG_ID = "bionicpro_reports_cdc_etl"
SCHEDULE_INTERVAL = "*/15 * * * *"  # Каждые 15 минут

# Connection IDs
TELEMETRY_CONN_ID = "bionicpro_telemetry_db"
CLICKHOUSE_CONN_ID = "bionicpro_clickhouse"

# Параметры ETL
ETL_LOOKBACK_HOURS = 2
ETL_BATCH_SIZE = 10000

# Reports Service (для инвалидации кэша)
REPORTS_SERVICE_URL = "http://reports-service:8001"

# ============================================================================
# Аргументы DAG
# ============================================================================
default_args = {
    "owner": "bionicpro-data-team",
    "depends_on_past": False,
    "email": ["data-alerts@bionicpro.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=30),
}


# ============================================================================
# Функция извлечения данных CRM из CDC (ClickHouse)
# ============================================================================
def extract_crm_from_cdc(**context) -> Dict[str, Any]:
    """
    Извлекает данные CRM из ClickHouse CDC таблиц.

    ВАЖНО: Данные уже находятся в ClickHouse благодаря CDC!
    Мы не обращаемся к CRM PostgreSQL, что снижает нагрузку на OLTP.
    """
    logger.info("Starting CRM data extraction from CDC (ClickHouse)")

    try:
        from clickhouse_driver import Client
    except ImportError:
        logger.error("clickhouse-driver not installed")
        raise

    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection(CLICKHOUSE_CONN_ID)

    client = Client(
        host=conn.host,
        port=conn.port or 9000,
        user=conn.login or "default",
        password=conn.password or "",
        database="reports",
    )

    # Читаем данные из CDC таблицы (уже в ClickHouse!)
    # Используем FINAL для получения актуальных данных после дедупликации
    query = """
        SELECT
            user_id,
            customer_name,
            customer_email,
            customer_region,
            customer_branch,
            prosthesis_id,
            prosthesis_serial,
            chip_id,
            prosthesis_model,
            prosthesis_category,
            firmware_version,
            last_updated_at
        FROM reports.cdc_customer_data FINAL
        WHERE chip_id != ''
    """

    logger.info("Executing CDC query on ClickHouse")
    result = client.execute(query, with_column_types=True)

    columns = [col[0] for col in result[1]] if len(result) > 1 else []
    data = result[0] if result else []

    # Если нет данных в CDC, пробуем fallback на прямой запрос к v_cdc_customer_prosthesis
    if not data:
        logger.warning("No data in cdc_customer_data, trying v_cdc_customer_prosthesis view")
        query = """
            SELECT
                user_id,
                customer_full_name AS customer_name,
                customer_email,
                customer_region,
                customer_branch,
                prosthesis_id,
                prosthesis_serial,
                chip_id,
                prosthesis_model,
                prosthesis_category,
                firmware_version,
                last_updated_at
            FROM reports.v_cdc_customer_prosthesis
        """
        result = client.execute(query, with_column_types=True)
        columns = [col[0] for col in result[1]] if len(result) > 1 else []
        data = result[0] if result else []

    if not data:
        logger.warning("No CDC data available yet. Waiting for Debezium initial snapshot.")
        context["ti"].xcom_push(key="crm_data", value="[]")
        return {"records_count": 0, "status": "no_cdc_data"}

    df = pd.DataFrame(data, columns=columns)
    logger.info(f"Extracted {len(df)} customer-prosthesis records from CDC")

    context["ti"].xcom_push(key="crm_data", value=df.to_json(orient="records", date_format="iso"))

    return {"records_count": len(df), "chip_ids": df["chip_id"].tolist()}


# ============================================================================
# Функция извлечения телеметрии (без изменений)
# ============================================================================
def extract_telemetry_data(**context) -> Dict[str, Any]:
    """
    Извлекает агрегированные данные телеметрии из Telemetry PostgreSQL.

    Телеметрия по-прежнему извлекается через ETL, т.к. это поток сырых данных,
    а не OLTP операции. CDC для телеметрии не требуется.
    """
    logger.info("Starting Telemetry data extraction")

    execution_date = context["execution_date"]
    lookback_time = execution_date - timedelta(hours=ETL_LOOKBACK_HOURS)

    telemetry_hook = PostgresHook(postgres_conn_id=TELEMETRY_CONN_ID)

    query = """
        SELECT
            chip_id,
            hour_start,
            report_date,
            report_hour,
            movements_count,
            successful_movements,
            success_rate,
            avg_response_time,
            min_response_time,
            max_response_time,
            avg_battery_level,
            min_battery_level,
            max_battery_level,
            avg_actuator_temp,
            max_actuator_temp,
            error_count,
            warning_count,
            avg_myo_amplitude,
            avg_connection_quality,
            updated_at
        FROM telemetry.v_hourly_telemetry
        WHERE hour_start >= %(lookback_time)s
        ORDER BY chip_id, hour_start
    """

    logger.info(f"Executing Telemetry query for data since {lookback_time}")
    df = telemetry_hook.get_pandas_df(query, parameters={"lookback_time": lookback_time})

    logger.info(f"Extracted {len(df)} hourly telemetry records")

    context["ti"].xcom_push(key="telemetry_data", value=df.to_json(orient="records", date_format="iso"))

    return {
        "records_count": len(df),
        "unique_chips": df["chip_id"].nunique() if len(df) > 0 else 0,
        "date_range": {
            "min": str(df["report_date"].min()) if len(df) > 0 else None,
            "max": str(df["report_date"].max()) if len(df) > 0 else None,
        },
    }


# ============================================================================
# Функция трансформации (JOIN CDC + Telemetry)
# ============================================================================
def transform_and_join(**context) -> Dict[str, Any]:
    """
    Объединяет данные CDC (CRM из ClickHouse) и телеметрии.

    JOIN по chip_id для связи телеметрии с данными клиента.
    """
    logger.info("Starting data transformation and join (CDC + Telemetry)")

    ti = context["ti"]

    crm_json = ti.xcom_pull(key="crm_data", task_ids="extract_crm_from_cdc")
    telemetry_json = ti.xcom_pull(key="telemetry_data", task_ids="extract_telemetry_data")

    if not crm_json or crm_json == "[]" or not telemetry_json:
        logger.warning("No data to transform")
        ti.xcom_push(key="mart_data", value="[]")
        return {"records_count": 0, "status": "no_data"}

    crm_df = pd.read_json(crm_json, orient="records")
    telemetry_df = pd.read_json(telemetry_json, orient="records")

    logger.info(f"CDC records: {len(crm_df)}, Telemetry records: {len(telemetry_df)}")

    if len(crm_df) == 0 or len(telemetry_df) == 0:
        logger.warning("Empty dataframes")
        ti.xcom_push(key="mart_data", value="[]")
        return {"records_count": 0, "status": "empty_data"}

    # JOIN телеметрии с CRM по chip_id
    mart_df = pd.merge(
        telemetry_df,
        crm_df,
        on="chip_id",
        how="inner"
    )

    logger.info(f"Joined records: {len(mart_df)}")

    if len(mart_df) == 0:
        logger.warning("No matching records after join")
        ti.xcom_push(key="mart_data", value="[]")
        return {"records_count": 0, "status": "no_matches"}

    # Выбираем колонки для витрины
    mart_df = mart_df[[
        "user_id",
        "prosthesis_id",
        "chip_id",
        "report_date",
        "report_hour",
        "customer_name",
        "customer_email",
        "customer_region",
        "customer_branch",
        "prosthesis_model",
        "prosthesis_category",
        "prosthesis_serial",
        "movements_count",
        "successful_movements",
        "success_rate",
        "avg_response_time",
        "min_response_time",
        "max_response_time",
        "avg_battery_level",
        "min_battery_level",
        "max_battery_level",
        "avg_actuator_temp",
        "max_actuator_temp",
        "error_count",
        "warning_count",
        "avg_connection_quality",
        "avg_myo_amplitude",
        "updated_at",
    ]]

    # Преобразуем типы данных
    mart_df["report_date"] = pd.to_datetime(mart_df["report_date"]).dt.date
    mart_df["report_hour"] = mart_df["report_hour"].astype(int)
    mart_df["prosthesis_id"] = mart_df["prosthesis_id"].astype(int)
    mart_df["movements_count"] = mart_df["movements_count"].fillna(0).astype(int)
    mart_df["successful_movements"] = mart_df["successful_movements"].fillna(0).astype(int)
    mart_df["error_count"] = mart_df["error_count"].fillna(0).astype(int)
    mart_df["warning_count"] = mart_df["warning_count"].fillna(0).astype(int)

    # Заполняем NULL значения
    numeric_cols = [
        "success_rate", "avg_response_time", "min_response_time", "max_response_time",
        "avg_battery_level", "min_battery_level", "max_battery_level",
        "avg_actuator_temp", "max_actuator_temp", "avg_connection_quality", "avg_myo_amplitude"
    ]
    for col in numeric_cols:
        mart_df[col] = mart_df[col].fillna(0)

    mart_df = mart_df.rename(columns={"updated_at": "source_updated_at"})

    logger.info(f"Transformation complete. Final records: {len(mart_df)}")

    ti.xcom_push(key="mart_data", value=mart_df.to_json(orient="records", date_format="iso"))

    return {
        "records_count": len(mart_df),
        "unique_users": mart_df["user_id"].nunique(),
        "date_range": {
            "min": str(mart_df["report_date"].min()),
            "max": str(mart_df["report_date"].max()),
        },
        "status": "success",
    }


# ============================================================================
# Функция загрузки в ClickHouse (без изменений)
# ============================================================================
def load_to_clickhouse(**context) -> Dict[str, Any]:
    """
    Загружает трансформированные данные в ClickHouse витрину.
    """
    logger.info("Starting load to ClickHouse")

    ti = context["ti"]
    mart_json = ti.xcom_pull(key="mart_data", task_ids="transform_and_join")

    if not mart_json or mart_json == "[]":
        logger.info("No data to load to ClickHouse")
        return {"records_loaded": 0, "status": "no_data"}

    mart_df = pd.read_json(mart_json, orient="records")

    if len(mart_df) == 0:
        logger.info("Empty dataframe, skipping load")
        return {"records_loaded": 0, "status": "empty_data"}

    logger.info(f"Loading {len(mart_df)} records to ClickHouse")

    try:
        from clickhouse_driver import Client
    except ImportError:
        logger.error("clickhouse-driver not installed")
        raise

    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection(CLICKHOUSE_CONN_ID)

    client = Client(
        host=conn.host,
        port=conn.port or 9000,
        user=conn.login or "default",
        password=conn.password or "",
        database="reports",
    )

    # Преобразуем даты
    mart_df["report_date"] = pd.to_datetime(mart_df["report_date"]).dt.strftime("%Y-%m-%d")
    mart_df["source_updated_at"] = pd.to_datetime(mart_df["source_updated_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    columns = [
        "user_id", "prosthesis_id", "chip_id", "report_date", "report_hour",
        "customer_name", "customer_email", "customer_region", "customer_branch",
        "prosthesis_model", "prosthesis_category", "prosthesis_serial",
        "movements_count", "successful_movements", "success_rate",
        "avg_response_time", "min_response_time", "max_response_time",
        "avg_battery_level", "min_battery_level", "max_battery_level",
        "avg_actuator_temp", "max_actuator_temp",
        "error_count", "warning_count", "avg_connection_quality", "avg_myo_amplitude",
        "source_updated_at"
    ]

    data = mart_df[columns].values.tolist()

    insert_query = f"""
        INSERT INTO reports.user_prosthesis_stats (
            {', '.join(columns)}, etl_processed_at
        ) VALUES
    """

    total_inserted = 0
    for i in range(0, len(data), ETL_BATCH_SIZE):
        batch = data[i : i + ETL_BATCH_SIZE]
        batch_with_timestamp = [tuple(row) + (datetime.now(),) for row in batch]
        client.execute(insert_query, batch_with_timestamp)
        total_inserted += len(batch)
        logger.info(f"Inserted batch {i // ETL_BATCH_SIZE + 1}: {len(batch)} records")

    logger.info(f"Total records loaded to ClickHouse: {total_inserted}")

    affected_user_ids = mart_df["user_id"].unique().tolist()
    ti.xcom_push(key="affected_user_ids", value=affected_user_ids)

    return {
        "records_loaded": total_inserted,
        "affected_users": len(affected_user_ids),
        "status": "success",
    }


# ============================================================================
# Функция инвалидации кэша (без изменений)
# ============================================================================
def invalidate_cdn_cache(**context) -> Dict[str, Any]:
    """
    Инвалидирует кэш S3/CDN для пользователей, чьи данные были обновлены.
    """
    import requests

    logger.info("Starting CDN cache invalidation")

    ti = context["ti"]
    affected_user_ids = ti.xcom_pull(key="affected_user_ids", task_ids="load_to_clickhouse")

    if not affected_user_ids:
        logger.info("No affected users to invalidate cache for")
        return {"invalidated_users": 0, "status": "no_users"}

    logger.info(f"Invalidating cache for {len(affected_user_ids)} users")

    try:
        response = requests.post(
            f"{REPORTS_SERVICE_URL}/api/reports/internal/invalidate",
            json={
                "user_ids": affected_user_ids,
                "invalidate_all": False,
            },
            headers={
                "Content-Type": "application/json",
                "X-Internal-Service": "airflow-cdc-etl",
            },
            timeout=60,
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"Cache invalidation successful: {result}")
            return {
                "invalidated_users": len(affected_user_ids),
                "details": result,
                "status": "success",
            }
        else:
            logger.warning(f"Cache invalidation returned status {response.status_code}")
            return {
                "invalidated_users": 0,
                "status": "partial_failure",
                "error": f"HTTP {response.status_code}",
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to call Reports Service: {e}")
        return {
            "invalidated_users": 0,
            "status": "failed",
            "error": str(e),
        }


# ============================================================================
# Определение DAG
# ============================================================================
with DAG(
    dag_id=DAG_ID,
    default_args=default_args,
    description="CDC ETL: Телеметрия + CRM (из CDC) -> ClickHouse витрина",
    schedule_interval=SCHEDULE_INTERVAL,
    start_date=days_ago(1),
    catchup=False,
    tags=["bionicpro", "etl", "reports", "clickhouse", "cdc"],
    max_active_runs=1,
    doc_md=__doc__,
) as dag:

    # Task 1: Извлечение данных CRM из CDC (ClickHouse)
    extract_crm = PythonOperator(
        task_id="extract_crm_from_cdc",
        python_callable=extract_crm_from_cdc,
        provide_context=True,
        doc_md="""
        ### Extract CRM from CDC (ClickHouse)
        Читает данные клиентов из ClickHouse CDC таблиц.

        **Важно:** Не обращается к CRM PostgreSQL!
        Данные поступают через Debezium CDC.
        """,
    )

    # Task 2: Извлечение телеметрии
    extract_telemetry = PythonOperator(
        task_id="extract_telemetry_data",
        python_callable=extract_telemetry_data,
        provide_context=True,
        doc_md="""
        ### Extract Telemetry Data
        Извлекает агрегированную почасовую телеметрию из PostgreSQL.
        """,
    )

    # Task 3: Трансформация
    transform = PythonOperator(
        task_id="transform_and_join",
        python_callable=transform_and_join,
        provide_context=True,
        doc_md="""
        ### Transform and Join (CDC + Telemetry)
        Объединяет CDC данные CRM и телеметрию по chip_id.
        """,
    )

    # Task 4: Загрузка
    load = PythonOperator(
        task_id="load_to_clickhouse",
        python_callable=load_to_clickhouse,
        provide_context=True,
        doc_md="""
        ### Load to ClickHouse
        Загружает объединённые данные в витрину.
        """,
    )

    # Task 5: Инвалидация кэша
    invalidate_cache = PythonOperator(
        task_id="invalidate_cdn_cache",
        python_callable=invalidate_cdn_cache,
        provide_context=True,
        doc_md="""
        ### Invalidate CDN Cache
        Инвалидирует кэш для обновлённых пользователей.
        """,
        trigger_rule="all_done",
    )

    # Зависимости:
    # CRM из CDC и телеметрия извлекаются параллельно
    # transform ждёт оба
    # load после transform
    # invalidate_cache после load
    [extract_crm, extract_telemetry] >> transform >> load >> invalidate_cache
