"""
ETL DAG: CRM + Telemetry → OLAP Data Mart
==========================================
Расписание: каждый день в 02:00 UTC
Логика:
  1. Extract  — читаем клиентов из CRM (PostgreSQL)
  2. Extract  — читаем телеметрию за расчётный период
  3. Transform — агрегируем телеметрию по client_id
  4. Load      — upsert витрины в OLAP (ClickHouse / PostgreSQL)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.dates import days_ago

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Константы подключений (задаются в Airflow Connections)
# ---------------------------------------------------------------------------
CRM_CONN_ID   = "write_to_postgres"    # PostgreSQL — источник CRM
OLAP_CONN_ID  = "olap"   # PostgreSQL / ClickHouse — приёмник OLAP

# ---------------------------------------------------------------------------
# Дефолтные аргументы DAG
# ---------------------------------------------------------------------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}

# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------
with DAG(
    dag_id="etl_crm_telemetry_to_olap",
    default_args=default_args,
    description="ETL: CRM + Telemetry → OLAP витрина отчётов по пользователям",
    # Запуск каждый день в 02:00 UTC (данные за вчера)
    schedule_interval="0 2 * * *",
    start_date=days_ago(1),
    catchup=False,                 # не гонять пропущенные запуски
    max_active_runs=1,
    tags=["etl", "crm", "telemetry", "olap", "reporting"],
    doc_md=__doc__,
) as dag:

    # -----------------------------------------------------------------------
    # TASK 0: Инициализация схемы (идемпотентно)
    # -----------------------------------------------------------------------
    def init_olap_schema(**context):
        """
        Создаём схему и таблицы в OLAP если они ещё не существуют.
        Запускается при каждом DAG Run, но безопасен благодаря IF NOT EXISTS.
        """
        olap = PostgresHook(postgres_conn_id=OLAP_CONN_ID)

        ddl = """
        -- --------------------------------
        -- Схемы
        -- --------------------------------
        CREATE SCHEMA IF NOT EXISTS staging;  -- временные данные ETL-процесса
        CREATE SCHEMA IF NOT EXISTS mart;     -- витрины для сервисов

        -- ----------------------------------------------------------------
        -- Staging: сырые клиенты из CRM
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS staging.crm_clients (
            client_id       BIGINT       NOT NULL,
            full_name       TEXT,
            email           TEXT,
            phone           TEXT,
            segment         VARCHAR(50),  -- 'premium' | 'standard' | 'trial'
            contract_start  DATE,
            contract_end    DATE,
            region          VARCHAR(100),
            loaded_at       TIMESTAMP    DEFAULT NOW(),
            PRIMARY KEY (client_id)
        );

        -- ----------------------------------------------------------------
        -- Staging: сырая телеметрия за расчётный период
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS staging.telemetry_raw (
            event_id        BIGINT,
            client_id       BIGINT       NOT NULL,
            device_id       VARCHAR(100),
            event_type      VARCHAR(100),
            value           DOUBLE PRECISION,
            event_ts        TIMESTAMP    NOT NULL,
            loaded_at       TIMESTAMP    DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_telemetry_raw_client
            ON staging.telemetry_raw (client_id, event_ts);

        -- ----------------------------------------------------------------
        -- Витрина: агрегаты телеметрии + CRM по пользователю / дню
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS mart.user_reports (
            -- Ключ витрины
            client_id           BIGINT       NOT NULL,
            report_date         DATE         NOT NULL,

            -- Данные из CRM
            full_name           TEXT,
            email               TEXT,
            segment             VARCHAR(50),
            region              VARCHAR(100),
            contract_active     BOOLEAN,

            -- Агрегаты телеметрии за report_date
            events_total        BIGINT       DEFAULT 0,
            events_distinct_devices BIGINT  DEFAULT 0,
            value_sum           DOUBLE PRECISION,
            value_avg           DOUBLE PRECISION,
            value_min           DOUBLE PRECISION,
            value_max           DOUBLE PRECISION,
            first_event_ts      TIMESTAMP,
            last_event_ts       TIMESTAMP,

            -- Служебные поля
            updated_at          TIMESTAMP    DEFAULT NOW(),

            PRIMARY KEY (client_id, report_date)
        );

        -- Индексы для быстрого доступа по пользователю и дате
        CREATE INDEX IF NOT EXISTS idx_user_reports_client
            ON mart.user_reports (client_id);
        CREATE INDEX IF NOT EXISTS idx_user_reports_date
            ON mart.user_reports (report_date DESC);
        CREATE INDEX IF NOT EXISTS idx_user_reports_segment
            ON mart.user_reports (segment, report_date DESC);
        """

        olap.run(ddl)
        logger.info("OLAP schema initialized successfully")

    # -----------------------------------------------------------------------
    # TASK 1: Extract CRM clients
    # -----------------------------------------------------------------------
    def extract_crm_clients(**context):
        """
        Читаем всех активных клиентов из CRM.
        Пушим список client_id в XCom для downstream-тасков.
        """
        crm = PostgresHook(postgres_conn_id=CRM_CONN_ID)
        olap = PostgresHook(postgres_conn_id=OLAP_CONN_ID)

        # Читаем клиентов из CRM
        rows = crm.get_records("""
            SELECT
                c.client_id,
                c.full_name,
                c.email,
                c.phone,
                c.segment,
                c.contract_start::DATE,
                c.contract_end::DATE,
                c.region
            FROM clients c
            WHERE c.deleted_at IS NULL
        """)

        if not rows:
            logger.warning("No CRM clients found — skipping")
            return []

        logger.info(f"Extracted {len(rows)} clients from CRM")

        # Truncate staging и bulk-insert
        olap.run("TRUNCATE TABLE staging.crm_clients")

        olap.insert_rows(
            table="staging.crm_clients",
            rows=rows,
            target_fields=[
                "client_id", "full_name", "email", "phone",
                "segment", "contract_start", "contract_end", "region",
            ],
            commit_every=1000,
        )

        client_ids = [r[0] for r in rows]
        # Пушим IDs в XCom для использования в следующих тасках
        context["ti"].xcom_push(key="client_ids", value=client_ids)
        logger.info(f"Pushed {len(client_ids)} client_ids to XCom")
        return client_ids

    # -----------------------------------------------------------------------
    # TASK 2: Extract Telemetry
    # -----------------------------------------------------------------------
    def extract_telemetry(**context):
        """
        Читаем телеметрию из источника за расчётный день (execution_date).
        Источник: отдельная БД телеметрии (или та же CRM-схема).
        """
        ti = context["ti"]
        # Расчётный день = дата запуска DAG минус 1 сутки (данные за вчера)
        execution_date: datetime = context["execution_date"]
        report_date = (execution_date - timedelta(days=1)).date()

        crm = PostgresHook(postgres_conn_id=CRM_CONN_ID)
        olap = PostgresHook(postgres_conn_id=OLAP_CONN_ID)

        logger.info(f"Extracting telemetry for date: {report_date}")

        # Читаем телеметрию за период
        rows = crm.get_records("""
            SELECT
                t.event_id,
                t.client_id,
                t.device_id,
                t.event_type,
                t.value,
                t.event_ts
            FROM telemetry t
            WHERE t.event_ts::DATE = %(report_date)s
              AND t.client_id IS NOT NULL
        """, parameters={"report_date": report_date})

        if not rows:
            logger.warning(f"No telemetry for {report_date}")
            ti.xcom_push(key="report_date", value=str(report_date))
            ti.xcom_push(key="telemetry_count", value=0)
            return

        logger.info(f"Extracted {len(rows)} telemetry events for {report_date}")

        # Очищаем staging за этот день и загружаем заново (идемпотентность)
        olap.run(
            "DELETE FROM staging.telemetry_raw WHERE event_ts::DATE = %(d)s",
            parameters={"d": report_date},
        )

        olap.insert_rows(
            table="staging.telemetry_raw",
            rows=rows,
            target_fields=[
                "event_id", "client_id", "device_id",
                "event_type", "value", "event_ts",
            ],
            commit_every=5000,
        )

        ti.xcom_push(key="report_date", value=str(report_date))
        ti.xcom_push(key="telemetry_count", value=len(rows))

    # -----------------------------------------------------------------------
    # TASK 3: Transform & Load → витрина mart.user_reports
    # -----------------------------------------------------------------------
    def transform_and_load(**context):
        """
        Агрегируем телеметрию по client_id + date,
        JOIN с CRM-данными из staging,
        UPSERT в mart.user_reports.
        """
        ti = context["ti"]
        report_date = ti.xcom_pull(task_ids="extract_telemetry", key="report_date")
        telemetry_count = ti.xcom_pull(task_ids="extract_telemetry", key="telemetry_count")

        if not report_date:
            logger.warning("No report_date in XCom — skipping transform")
            return

        if telemetry_count == 0:
            logger.warning(f"No telemetry for {report_date} — upserting CRM-only rows")

        olap = PostgresHook(postgres_conn_id=OLAP_CONN_ID)

        upsert_sql = """
        INSERT INTO mart.user_reports (
            client_id,
            report_date,
            full_name,
            email,
            segment,
            region,
            contract_active,
            events_total,
            events_distinct_devices,
            value_sum,
            value_avg,
            value_min,
            value_max,
            first_event_ts,
            last_event_ts,
            updated_at
        )
        SELECT
            c.client_id,
            %(report_date)s::DATE                           AS report_date,

            -- CRM поля
            c.full_name,
            c.email,
            c.segment,
            c.region,
            (
                c.contract_start <= %(report_date)s::DATE
                AND (c.contract_end IS NULL OR c.contract_end >= %(report_date)s::DATE)
            )                                               AS contract_active,

            -- Агрегаты телеметрии (0 если данных нет)
            COALESCE(t.events_total, 0)                     AS events_total,
            COALESCE(t.events_distinct_devices, 0)          AS events_distinct_devices,
            t.value_sum,
            t.value_avg,
            t.value_min,
            t.value_max,
            t.first_event_ts,
            t.last_event_ts,
            NOW()                                           AS updated_at

        FROM staging.crm_clients c
        LEFT JOIN (
            -- Агрегация телеметрии за расчётный день
            SELECT
                client_id,
                COUNT(*)                        AS events_total,
                COUNT(DISTINCT device_id)       AS events_distinct_devices,
                SUM(value)                      AS value_sum,
                AVG(value)                      AS value_avg,
                MIN(value)                      AS value_min,
                MAX(value)                      AS value_max,
                MIN(event_ts)                   AS first_event_ts,
                MAX(event_ts)                   AS last_event_ts
            FROM staging.telemetry_raw
            WHERE event_ts::DATE = %(report_date)s::DATE
            GROUP BY client_id
        ) t ON t.client_id = c.client_id

        ON CONFLICT (client_id, report_date) DO UPDATE SET
            full_name               = EXCLUDED.full_name,
            email                   = EXCLUDED.email,
            segment                 = EXCLUDED.segment,
            region                  = EXCLUDED.region,
            contract_active         = EXCLUDED.contract_active,
            events_total            = EXCLUDED.events_total,
            events_distinct_devices = EXCLUDED.events_distinct_devices,
            value_sum               = EXCLUDED.value_sum,
            value_avg               = EXCLUDED.value_avg,
            value_min               = EXCLUDED.value_min,
            value_max               = EXCLUDED.value_max,
            first_event_ts          = EXCLUDED.first_event_ts,
            last_event_ts           = EXCLUDED.last_event_ts,
            updated_at              = NOW()
        """

        olap.run(upsert_sql, parameters={"report_date": report_date})
        logger.info(f"mart.user_reports upserted for {report_date}")

        # Проверяем результат
        count = olap.get_first(
            "SELECT COUNT(*) FROM mart.user_reports WHERE report_date = %(d)s",
            parameters={"d": report_date},
        )[0]
        logger.info(f"Rows in mart.user_reports for {report_date}: {count}")

    # -----------------------------------------------------------------------
    # TASK 4: Data Quality Check
    # -----------------------------------------------------------------------
    def data_quality_check(**context):
        """
        Базовые проверки качества данных после загрузки.
        Падаем с ошибкой, если что-то пошло не так.
        """
        ti = context["ti"]
        report_date = ti.xcom_pull(task_ids="extract_telemetry", key="report_date")

        if not report_date:
            return

        olap = PostgresHook(postgres_conn_id=OLAP_CONN_ID)

        checks = [
            # 1. В витрине должны быть строки
            (
                "SELECT COUNT(*) FROM mart.user_reports WHERE report_date = %(d)s",
                lambda v: v > 0,
                "mart.user_reports пустая для отчётной даты",
            ),
            # 2. Не должно быть дублей (client_id, report_date)
            (
                """
                SELECT COUNT(*) FROM (
                    SELECT client_id, COUNT(*) AS cnt
                    FROM mart.user_reports
                    WHERE report_date = %(d)s
                    GROUP BY client_id HAVING COUNT(*) > 1
                ) dupes
                """,
                lambda v: v == 0,
                "Обнаружены дубли (client_id, report_date) в mart.user_reports",
            ),
            # 3. client_id не должен быть NULL
            (
                "SELECT COUNT(*) FROM mart.user_reports WHERE client_id IS NULL AND report_date = %(d)s",
                lambda v: v == 0,
                "Обнаружены NULL client_id в mart.user_reports",
            ),
        ]

        failed = []
        for sql, check_fn, msg in checks:
            value = olap.get_first(sql, parameters={"d": report_date})[0]
            if not check_fn(value):
                failed.append(f"FAILED [{value}]: {msg}")
                logger.error(f"DQ check failed: {msg} (value={value})")
            else:
                logger.info(f"DQ check OK: {msg} (value={value})")

        if failed:
            raise ValueError("Data quality checks failed:\n" + "\n".join(failed))

        logger.info("All data quality checks passed ✓")

    # -----------------------------------------------------------------------
    # Определяем операторы
    # -----------------------------------------------------------------------
    t0_init = PythonOperator(
        task_id="init_olap_schema",
        python_callable=init_olap_schema,
        doc_md="Создаёт схемы и таблицы в OLAP если не существуют (идемпотентно)",
    )

    t1_extract_crm = PythonOperator(
        task_id="extract_crm_clients",
        python_callable=extract_crm_clients,
        doc_md="Извлекает клиентов из CRM PostgreSQL → staging.crm_clients",
    )

    t2_extract_telemetry = PythonOperator(
        task_id="extract_telemetry",
        python_callable=extract_telemetry,
        doc_md="Извлекает телеметрию за расчётный день → staging.telemetry_raw",
    )

    t3_transform_load = PythonOperator(
        task_id="transform_and_load",
        python_callable=transform_and_load,
        doc_md="JOIN CRM + телеметрия, агрегация, UPSERT → mart.user_reports",
    )

    t4_dq_check = PythonOperator(
        task_id="data_quality_check",
        python_callable=data_quality_check,
        doc_md="Проверки качества данных в mart.user_reports",
    )

    # -----------------------------------------------------------------------
    # Граф зависимостей
    # -----------------------------------------------------------------------
    #
    #   init_schema
    #        │
    #   ┌────┴─────┐
    #   │          │
    # extract_crm  extract_telemetry   ← параллельно
    #   │          │
    #   └────┬─────┘
    #        │
    #   transform_and_load
    #        │
    #   data_quality_check
    #
    t0_init >> [t1_extract_crm, t2_extract_telemetry] >> t3_transform_load >> t4_dq_check
