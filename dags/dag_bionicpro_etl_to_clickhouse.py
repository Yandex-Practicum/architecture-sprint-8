from __future__ import annotations

import base64
import http.client
import json
import os
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import psycopg2
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator

DAG_DIR = os.path.dirname(os.path.abspath(__file__))


def _pg_conn():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_ETL_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_ETL_PORT", "5432")),
        dbname="sample",
        user="airflow",
        password="airflow",
    )


def _ch_http_base() -> str:
    """Базовый URL без завершающего слэша. CLICKHOUSE_HTTP_URL либо host/port из env.

    В compose для scheduler задано network_mode: service:clickhouse и CLICKHOUSE_HOST=127.0.0.1.
    """
    explicit = (os.environ.get("CLICKHOUSE_HTTP_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    user = (os.environ.get("CLICKHOUSE_USER") or "default").strip() or "default"
    password = os.environ.get("CLICKHOUSE_PASSWORD")
    password = "" if password is None else str(password)
    host = (os.environ.get("CLICKHOUSE_HOST") or "clickhouse").strip() or "clickhouse"
    port = (os.environ.get("CLICKHOUSE_HTTP_PORT") or "8123").strip() or "8123"
    if password:
        u = urllib.parse.quote(user, safe="")
        p = urllib.parse.quote(password, safe="")
        return f"http://{u}:{p}@{host}:{port}"
    return f"http://{host}:{port}"


def _ch_post_sql(sql: str, timeout_sec: int = 300) -> None:
    """ClickHouse HTTP: POST / с телом = SQL. Через http.client — без urllib opener и HTTP(S)_PROXY."""
    base = _ch_http_base().rstrip("/")
    if not base.lower().startswith(("http://", "https://")):
        base = "http://" + base
    parts = urllib.parse.urlsplit(base)
    hostname = parts.hostname
    if not hostname:
        raise RuntimeError(f"Некорректный ClickHouse URL: {base!r}")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    conn_cls = (
        http.client.HTTPSConnection
        if parts.scheme == "https"
        else http.client.HTTPConnection
    )

    headers = {"Content-Type": "text/plain; charset=utf-8"}
    if parts.username is not None or parts.password is not None:
        raw = f"{parts.username or ''}:{parts.password or ''}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.standard_b64encode(raw).decode(
            "ascii"
        )

    body = sql.encode("utf-8")
    conn = conn_cls(hostname, port, timeout=timeout_sec)
    try:
        conn.request("POST", "/", body, headers)
        resp = conn.getresponse()
        payload = resp.read()
        if resp.status >= 400:
            detail = payload.decode("utf-8", errors="replace")
            raise RuntimeError(f"ClickHouse HTTP {resp.status}: {detail}")
    except OSError as e:
        raise RuntimeError(
            f"Не удаётся подключиться к ClickHouse ({base}): {e}. "
            "Scheduler: network_mode: service:clickhouse и CLICKHOUSE_HOST=127.0.0.1, либо CLICKHOUSE_HTTP_URL."
        ) from e
    finally:
        conn.close()


def _ch_insert_json_each_row(table_sql_prefix: str, rows: List[dict]) -> None:
    lines = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    body = f"{table_sql_prefix}\n{lines}"
    _ch_post_sql(body, timeout_sec=300)


def build_mart_for_day(**context: Any) -> None:
    ds: str = context["ds"]
    logical_day = date.fromisoformat(ds)
    loaded_at = datetime.now(timezone.utc).replace(tzinfo=None)

    start_utc = datetime(
        logical_day.year, logical_day.month, logical_day.day, tzinfo=timezone.utc
    )
    end_utc = start_utc + timedelta(days=1)

    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute(
            """
            SELECT
              c.customer_id,
              c.keycloak_sub,
              p.prosthesis_id,
              p.serial_number,
              p.model,
              COALESCE(
                (SELECT COUNT(*)::integer
                 FROM crm_order o
                 WHERE o.customer_id = c.customer_id AND o.created_at <= %s),
                0
              ) AS orders_count,
              COALESCE(
                (SELECT SUM(o.total)::double precision
                 FROM crm_order o
                 WHERE o.customer_id = c.customer_id AND o.created_at <= %s),
                0
              ) AS orders_sum
            FROM crm_customer c
            INNER JOIN crm_prosthesis p ON p.customer_id = c.customer_id
            """,
            (logical_day, logical_day),
        )
        crm_rows: List[Tuple[Any, ...]] = cur.fetchall()

        cur.execute(
            """
            SELECT
              prosthesis_id,
              COUNT(*)::bigint,
              COALESCE(
                AVG(metric_value) FILTER (WHERE metric_name = 'signal_quality'),
                0
              )::double precision
            FROM telemetry_event
            WHERE event_time >= %s AND event_time < %s
            GROUP BY prosthesis_id
            """,
            (start_utc, end_utc),
        )
        tel_map: Dict[int, Tuple[int, float]] = {
            int(r[0]): (int(r[1]), float(r[2])) for r in cur.fetchall()
        }
        cur.close()
    finally:
        pg.close()

    _ch_post_sql(
        "ALTER TABLE bionicpro.mart_user_prosthesis_report DELETE WHERE "
        f"report_date = toDate('{ds}') SETTINGS mutations_sync = 1"
    )

    insert_rows: List[dict] = []
    for row in crm_rows:
        cid, ksub, pid, serial, model, ocnt, osum = row
        tev, avg_sig = tel_map.get(int(pid), (0, 0.0))
        insert_rows.append(
            {
                "report_date": logical_day.isoformat(),
                "keycloak_sub": str(ksub),
                "customer_id": int(cid),
                "prosthesis_id": int(pid),
                "serial_number": str(serial),
                "model": str(model),
                "orders_count": int(ocnt),
                "orders_sum": float(osum),
                "telemetry_events": int(tev),
                "avg_signal_quality": float(avg_sig),
                "loaded_at": loaded_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    if not insert_rows:
        return

    _ch_insert_json_each_row(
        "INSERT INTO bionicpro.mart_user_prosthesis_report FORMAT JSONEachRow",
        insert_rows,
    )


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2024, 12, 1),
}

with DAG(
    dag_id="bionicpro_crm_telemetry_to_clickhouse",
    default_args=default_args,
    description="ETL: CRM + телеметрия (PostgreSQL) -> витрина ClickHouse",
    schedule_interval="0 3 * * *",
    catchup=False,
    tags=["bionicpro", "etl", "clickhouse"],
    max_active_runs=1,
    template_searchpath=[DAG_DIR],
) as dag:
    # Том Postgres мог быть создан до db/02-sample-oltp.sql — создаём схему при каждом прогоне (идемпотентно)
    ensure_oltp_schema = PostgresOperator(
        task_id="ensure_oltp_schema",
        postgres_conn_id="write_to_postgres",
        sql="sql/oltp_bionicpro_bootstrap.sql",
        split_statements=True,
        autocommit=True,
    )

    build_mart = PythonOperator(
        task_id="build_mart_for_logical_day",
        python_callable=build_mart_for_day,
    )

    ensure_oltp_schema >> build_mart
