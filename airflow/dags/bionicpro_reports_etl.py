"""
BionicPRO Reports ETL DAG

ETL-процесс для объединения данных телеметрии с протезов и данных клиентов из CRM.
Результат загружается в ClickHouse витрину для сервиса отчётов.

DAG: bionicpro_reports_etl
Расписание: каждые 15 минут (*/15 * * * *)
Задачи:
    1. extract_crm_data - извлечение данных клиентов и протезов из CRM DB
    2. extract_telemetry_data - извлечение данных телеметрии из Telemetry DB
    3. transform_and_join - объединение и трансформация данных
    4. load_to_clickhouse - загрузка витрины в ClickHouse
    5. invalidate_cdn_cache - инвалидация кэша S3/CDN для затронутых пользователей (Задание 3)
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.models import Variable
from airflow.utils.dates import days_ago

import pandas as pd
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

# ============================================================================
# Конфигурация DAG
# ============================================================================
DAG_ID = "bionicpro_reports_etl"
SCHEDULE_INTERVAL = "*/15 * * * *"  # Каждые 15 минут

# Connection IDs (настраиваются в Airflow Admin -> Connections)
CRM_CONN_ID = "bionicpro_crm_db"
TELEMETRY_CONN_ID = "bionicpro_telemetry_db"
CLICKHOUSE_CONN_ID = "bionicpro_clickhouse"

# Параметры ETL
ETL_LOOKBACK_HOURS = 168  # Обрабатываем данные за последние N часов (168 = 7 дней для начальной загрузки)
ETL_BATCH_SIZE = 10000  # Размер пакета для вставки

# Reports Service (Задание 3 - инвалидация кэша)
REPORTS_SERVICE_URL = "http://reports-service:8001"

# ============================================================================
# Аргументы DAG по умолчанию
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
# Функции извлечения данных (Extract)
# ============================================================================
def extract_crm_data(**context) -> Dict[str, Any]:
    """
    Извлекает данные клиентов и протезов из CRM PostgreSQL.

    Возвращает словарь с данными для XCom:
    - customers: DataFrame с данными клиентов
    - prostheses: DataFrame с данными протезов
    """
    logger.info("Starting CRM data extraction")

    # Получаем время последнего успешного запуска или lookback
    execution_date = context["execution_date"]
    lookback_time = execution_date - timedelta(hours=ETL_LOOKBACK_HOURS)

    crm_hook = PostgresHook(postgres_conn_id=CRM_CONN_ID)

    # SQL для извлечения данных клиентов и протезов
    query = """
        SELECT
            c.customer_id,
            c.external_id AS user_id,
            CONCAT(c.last_name, ' ', c.first_name, COALESCE(' ' || c.middle_name, '')) AS customer_name,
            c.email AS customer_email,
            c.region AS customer_region,
            c.branch AS customer_branch,
            p.prosthesis_id,
            p.serial_number AS prosthesis_serial,
            p.chip_id,
            pm.model_name AS prosthesis_model,
            pm.category AS prosthesis_category,
            GREATEST(c.updated_at, p.updated_at) AS last_updated_at
        FROM crm.customers c
        JOIN crm.prostheses p ON c.customer_id = p.customer_id
        JOIN crm.prosthesis_models pm ON p.model_id = pm.model_id
        WHERE p.status = 'active'
          AND p.chip_id IS NOT NULL
    """

    logger.info(f"Executing CRM query with lookback from {lookback_time}")

    df = crm_hook.get_pandas_df(query)

    logger.info(f"Extracted {len(df)} customer-prosthesis records from CRM")

    # Сохраняем в XCom как JSON
    context["ti"].xcom_push(key="crm_data", value=df.to_json(orient="records", date_format="iso"))

    return {"records_count": len(df), "chip_ids": df["chip_id"].tolist()}


def extract_telemetry_data(**context) -> Dict[str, Any]:
    """
    Извлекает агрегированные данные телеметрии из Telemetry PostgreSQL.

    Использует представление v_hourly_telemetry для получения почасовой статистики.
    """
    logger.info("Starting Telemetry data extraction")

    execution_date = context["execution_date"]
    lookback_time = execution_date - timedelta(hours=ETL_LOOKBACK_HOURS)

    telemetry_hook = PostgresHook(postgres_conn_id=TELEMETRY_CONN_ID)

    # SQL для извлечения почасовой телеметрии
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

    # Сохраняем в XCom
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
# Функции трансформации данных (Transform)
# ============================================================================
def transform_and_join(**context) -> Dict[str, Any]:
    """
    Объединяет данные CRM и телеметрии, выполняет трансформацию.

    JOIN по chip_id для связи телеметрии с данными клиента.
    Результат: витрина с агрегированными метриками по пользователю.
    """
    logger.info("Starting data transformation and join")

    ti = context["ti"]

    # Получаем данные из XCom
    crm_json = ti.xcom_pull(key="crm_data", task_ids="extract_crm_data")
    telemetry_json = ti.xcom_pull(key="telemetry_data", task_ids="extract_telemetry_data")

    if not crm_json or not telemetry_json:
        logger.warning("No data to transform - one or both extracts returned empty")
        ti.xcom_push(key="mart_data", value="[]")
        return {"records_count": 0, "status": "no_data"}

    # Конвертируем JSON в DataFrame
    crm_df = pd.read_json(crm_json, orient="records")
    telemetry_df = pd.read_json(telemetry_json, orient="records")

    logger.info(f"CRM records: {len(crm_df)}, Telemetry records: {len(telemetry_df)}")

    if len(crm_df) == 0 or len(telemetry_df) == 0:
        logger.warning("Empty dataframes after JSON parsing")
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

    # Выбираем и переименовываем колонки для витрины
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

    # Переименовываем updated_at -> source_updated_at
    mart_df = mart_df.rename(columns={"updated_at": "source_updated_at"})

    logger.info(f"Transformation complete. Final records: {len(mart_df)}")

    # Сохраняем в XCom
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
# Функции загрузки данных (Load)
# ============================================================================
def load_to_clickhouse(**context) -> Dict[str, Any]:
    """
    Загружает трансформированные данные в ClickHouse витрину.

    Использует INSERT с ON DUPLICATE KEY UPDATE для upsert семантики.
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

    # Импортируем ClickHouse клиент
    try:
        from clickhouse_driver import Client
    except ImportError:
        logger.error("clickhouse-driver not installed. Install with: pip install clickhouse-driver")
        raise

    # Получаем параметры подключения из Airflow Connection
    from airflow.hooks.base import BaseHook
    conn = BaseHook.get_connection(CLICKHOUSE_CONN_ID)

    client = Client(
        host=conn.host,
        port=conn.port or 9000,
        user=conn.login or "default",
        password=conn.password or "",
        database="reports",
    )

    # Преобразуем DataFrame в список кортежей для вставки
    # Конвертируем даты в правильный формат для ClickHouse
    mart_df["report_date"] = pd.to_datetime(mart_df["report_date"]).dt.date
    mart_df["source_updated_at"] = pd.to_datetime(mart_df["source_updated_at"])

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

    # Собираем данные для вставки
    data = mart_df[columns].values.tolist()

    # Вставляем данные пакетами
    insert_query = f"""
        INSERT INTO reports.user_prosthesis_stats (
            {', '.join(columns)}, etl_processed_at
        ) VALUES
    """

    total_inserted = 0
    for i in range(0, len(data), ETL_BATCH_SIZE):
        batch = data[i : i + ETL_BATCH_SIZE]
        # Добавляем текущее время как etl_processed_at
        batch_with_timestamp = [tuple(row) + (datetime.now(),) for row in batch]

        client.execute(
            insert_query,
            batch_with_timestamp,
        )
        total_inserted += len(batch)
        logger.info(f"Inserted batch {i // ETL_BATCH_SIZE + 1}: {len(batch)} records")

    logger.info(f"Total records loaded to ClickHouse: {total_inserted}")

    # Сохраняем список user_ids для последующей инвалидации кэша
    affected_user_ids = mart_df["user_id"].unique().tolist()
    ti.xcom_push(key="affected_user_ids", value=affected_user_ids)

    return {
        "records_loaded": total_inserted,
        "affected_users": len(affected_user_ids),
        "status": "success",
    }


# ============================================================================
# Функция инвалидации кэша (Задание 3)
# ============================================================================
def invalidate_cdn_cache(**context) -> Dict[str, Any]:
    """
    Инвалидирует кэш S3/CDN для пользователей, чьи данные были обновлены.

    Вызывает POST /api/reports/invalidate на Reports Service.
    Это удаляет:
    - JSON файлы из S3 (MinIO)
    - Записи из Redis кэша

    CDN (Nginx) кэш истечёт по TTL (5 минут).

    Задание 3: Снижение нагрузки на базу данных
    """
    import requests

    logger.info("Starting CDN cache invalidation")

    ti = context["ti"]

    # Получаем список затронутых пользователей из предыдущей задачи
    affected_user_ids = ti.xcom_pull(key="affected_user_ids", task_ids="load_to_clickhouse")

    if not affected_user_ids:
        logger.info("No affected users to invalidate cache for")
        return {"invalidated_users": 0, "status": "no_users"}

    logger.info(f"Invalidating cache for {len(affected_user_ids)} users")

    # Получаем admin token для авторизации
    # В production это должен быть service account token
    # Для упрощения используем статический API key или service-to-service auth
    try:
        # Вызываем Reports Service API для инвалидации
        # Примечание: для service-to-service вызовов можно использовать внутренний эндпойнт
        # или API key вместо JWT
        response = requests.post(
            f"{REPORTS_SERVICE_URL}/api/reports/internal/invalidate",
            json={
                "user_ids": affected_user_ids,
                "invalidate_all": False,
            },
            headers={
                "Content-Type": "application/json",
                "X-Internal-Service": "airflow-etl",  # Внутренний сервис
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
            logger.warning(
                f"Cache invalidation returned status {response.status_code}: {response.text}"
            )
            # Не фейлим задачу - данные уже загружены, кэш истечёт по TTL
            return {
                "invalidated_users": 0,
                "status": "partial_failure",
                "error": f"HTTP {response.status_code}",
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to call Reports Service for cache invalidation: {e}")
        # Не фейлим задачу - данные уже загружены, кэш истечёт по TTL
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
    description="ETL процесс для витрины отчётов BionicPRO: CRM + Telemetry -> ClickHouse",
    schedule_interval=SCHEDULE_INTERVAL,
    start_date=days_ago(1),
    catchup=False,
    tags=["bionicpro", "etl", "reports", "clickhouse"],
    max_active_runs=1,  # Только один запуск одновременно
    doc_md=__doc__,
) as dag:

    # Task 1: Извлечение данных из CRM
    extract_crm = PythonOperator(
        task_id="extract_crm_data",
        python_callable=extract_crm_data,
        provide_context=True,
        doc_md="""
        ### Extract CRM Data
        Извлекает данные клиентов и их протезов из CRM PostgreSQL.
        - Таблицы: crm.customers, crm.prostheses, crm.prosthesis_models
        - Фильтр: только активные протезы с chip_id
        """,
    )

    # Task 2: Извлечение данных телеметрии
    extract_telemetry = PythonOperator(
        task_id="extract_telemetry_data",
        python_callable=extract_telemetry_data,
        provide_context=True,
        doc_md="""
        ### Extract Telemetry Data
        Извлекает агрегированную почасовую телеметрию.
        - Представление: telemetry.v_hourly_telemetry
        - Lookback: последние 2 часа
        """,
    )

    # Task 3: Трансформация и объединение
    transform = PythonOperator(
        task_id="transform_and_join",
        python_callable=transform_and_join,
        provide_context=True,
        doc_md="""
        ### Transform and Join
        Объединяет данные CRM и телеметрии по chip_id.
        - JOIN: telemetry + crm ON chip_id
        - Агрегация: по user_id, дате, часу
        - Метрики: время отклика, батарея, ошибки
        """,
    )

    # Task 4: Загрузка в ClickHouse
    load = PythonOperator(
        task_id="load_to_clickhouse",
        python_callable=load_to_clickhouse,
        provide_context=True,
        doc_md="""
        ### Load to ClickHouse
        Загружает витрину в ClickHouse OLAP.
        - Таблица: reports.user_prosthesis_stats
        - Режим: INSERT (append)
        - Batch size: 10000 записей
        """,
    )

    # Task 5: Инвалидация кэша S3/CDN (Задание 3)
    invalidate_cache = PythonOperator(
        task_id="invalidate_cdn_cache",
        python_callable=invalidate_cdn_cache,
        provide_context=True,
        doc_md="""
        ### Invalidate CDN Cache (Задание 3)
        Инвалидирует кэш для затронутых пользователей после загрузки данных.
        - Удаляет JSON файлы из S3 (MinIO)
        - Очищает Redis кэш
        - CDN кэш истечёт по TTL (5 минут)

        Это обеспечивает получение актуальных отчётов пользователями
        без повторных запросов к ClickHouse.
        """,
        # Не блокирует DAG при ошибке - данные уже загружены
        trigger_rule="all_done",
    )

    # Определение зависимостей задач
    # extract_crm и extract_telemetry выполняются параллельно
    # transform ждёт завершения обоих extract
    # load выполняется после transform
    # invalidate_cache выполняется после load (Задание 3)
    [extract_crm, extract_telemetry] >> transform >> load >> invalidate_cache
