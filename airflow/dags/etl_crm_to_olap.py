from datetime import date, datetime, timedelta
from typing import Dict, List, Any

import requests
from airflow import DAG
from airflow.decorators import task
from airflow.hooks.base import BaseHook
from airflow.providers.postgres.hooks.postgres import PostgresHook

CRM_CONN_ID = "crm_db"
TELEMETRY_CONN_ID = "telemetry_db"
CLICKHOUSE_CONN_ID = "clickhouse_http"

DEFAULT_ARGS = {
    "owner": "bionicpro",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
    "email": ["alerts@bionicpro.ru"],
}


def _clickhouse_execute(sql: str, data_payload: bytes = None) -> requests.Response:
    conn = BaseHook.get_connection(CLICKHOUSE_CONN_ID)
    base_url = f"http://{conn.host}:{conn.port or 8123}/"
    params = {
        "database": conn.schema or "olap_db",
        "default_format": "TabSeparatedWithNamesAndTypes",
        "query": sql,
    }
    auth = (conn.login, conn.password) if conn.login else None
    resp = requests.post(base_url, params=params, auth=auth, data=data_payload, timeout=60)
    resp.raise_for_status()
    return resp


def _clickhouse_insert_rows(table: str, columns: List[str], rows: List[List[Any]]) -> None:
    if not rows:
        return
    header_sql = f"INSERT INTO {table} ({', '.join(columns)}) FORMAT TabSeparated"
    lines = []
    for row in rows:
        formatted_row = []
        for val in row:
            if val is None:
                formatted_row.append(r"\N")
            elif isinstance(val, datetime):
                formatted_row.append(val.strftime("%Y-%m-%d %H:%M:%S"))
            elif isinstance(val, date):
                formatted_row.append(val.strftime("%Y-%m-%d"))
            elif isinstance(val, bool):
                formatted_row.append("1" if val else "0")
            else:
                s = str(val).replace("\t", "\\t").replace("\n", "\\n")
                formatted_row.append(s)
        lines.append("\t".join(formatted_row))
    data_payload = ("\n".join(lines) + "\n").encode("utf-8")
    _clickhouse_execute(header_sql, data_payload=data_payload)


@task
def extract_crm_customers() -> List[Dict[str, Any]]:
    pg_hook = PostgresHook(postgres_conn_id=CRM_CONN_ID)
    rows = pg_hook.get_records("""
        SELECT
            customer_id,
            full_name,
            email,
            prosthesis_model,
            region,
            purchase_date,
            warranty_end_date
        FROM crm_customers
        ORDER BY customer_id
    """)
    columns = ["customer_id", "full_name", "email", "prosthesis_model",
               "region", "purchase_date", "warranty_end_date"]
    return [dict(zip(columns, row)) for row in rows]


@task
def extract_telemetry_aggregates() -> List[Dict[str, Any]]:
    pg_hook = PostgresHook(postgres_conn_id=TELEMETRY_CONN_ID)
    rows = pg_hook.get_records("""
        SELECT
            s.customer_id,
            COUNT(DISTINCT s.session_id)                                                          AS total_sessions,
            COALESCE(SUM(s.movements_count), 0)                                                   AS total_movements,
            COALESCE(SUM(s.errors_count), 0)                                                      AS total_errors,
            COALESCE(EXTRACT(EPOCH FROM SUM(s.ended_at - s.started_at)) / 3600, 0)                AS total_usage_hours,
            MIN(DATE(s.started_at))                                                                AS first_active_date,
            MAX(DATE(s.started_at))                                                                AS last_active_date,
            COALESCE(AVG(s.battery_start - s.battery_end), 0)                                     AS avg_battery_drain,
            COALESCE(
                (SELECT e2.movement_type
                 FROM telemetry_events e2
                          JOIN telemetry_sessions s2 ON s2.session_id = e2.session_id
                 WHERE s2.customer_id = s.customer_id
                 GROUP BY e2.movement_type
                 ORDER BY COUNT(*) DESC
                 LIMIT 1), 'unknown'
            )                                                                                     AS most_common_movement
        FROM telemetry_sessions s
        GROUP BY s.customer_id
        ORDER BY s.customer_id
    """)
    columns = ["customer_id", "total_sessions", "total_movements", "total_errors",
               "total_usage_hours", "first_active_date", "last_active_date",
               "avg_battery_drain", "most_common_movement"]
    return [dict(zip(columns, row)) for row in rows]


@task
def build_data_mart(
    customers: List[Dict[str, Any]],
    telemetry: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    telemetry_by_customer = {t["customer_id"]: t for t in telemetry}
    today = datetime.now().date()

    mart_rows: List[Dict[str, Any]] = []
    for c in customers:
        cid = c["customer_id"]
        t = telemetry_by_customer.get(cid, {})

        total_hours = float(t.get("total_usage_hours", 0))
        total_sessions = int(t.get("total_sessions", 0))
        avg_daily_minutes = 0.0
        if t.get("first_active_date") and t.get("last_active_date"):
            f_date = datetime.strptime(str(t["first_active_date"]), "%Y-%m-%d").date() if isinstance(t["first_active_date"], str) else t["first_active_date"]
            l_date = datetime.strptime(str(t["last_active_date"]), "%Y-%m-%d").date() if isinstance(t["last_active_date"], str) else t["last_active_date"]
            days_active = (l_date - f_date).days + 1
            avg_daily_minutes = (total_hours * 60) / max(days_active, 1)

        purchase_date = c["purchase_date"]
        warranty_end = c["warranty_end_date"]

        p_date_obj = datetime.strptime(str(purchase_date), "%Y-%m-%d").date() if isinstance(purchase_date, str) else purchase_date
        w_date_obj = datetime.strptime(str(warranty_end), "%Y-%m-%d").date() if isinstance(warranty_end, str) and warranty_end else warranty_end

        warranty_status = "active" if w_date_obj and w_date_obj >= today else "expired"

        row = {
            "customer_id": cid,
            "customer_name": c["full_name"],
            "customer_email": c["email"],
            "prosthesis_model": c["prosthesis_model"],
            "region": c["region"],
            "purchase_date": str(p_date_obj),
            "warranty_end_date": str(w_date_obj) if w_date_obj else None,
            "warranty_status": warranty_status,
            "total_usage_hours": round(total_hours, 2),
            "avg_daily_usage_minutes": round(avg_daily_minutes, 1),
            "total_sessions": total_sessions,
            "total_movements": int(t.get("total_movements", 0)),
            "avg_movements_per_session": round(
                int(t.get("total_movements", 0)) / max(total_sessions, 1), 1
            ),
            "total_errors": int(t.get("total_errors", 0)),
            "errors_per_session": round(
                int(t.get("total_errors", 0)) / max(total_sessions, 1), 2
            ),
            "last_active_date": str(t.get("last_active_date") or p_date_obj),
            "battery_health_avg": round(float(t.get("avg_battery_drain", 0)), 1),
            "most_common_movement": t.get("most_common_movement", "unknown"),
            "data_as_of_date": str(today),
        }
        mart_rows.append(row)
    return mart_rows


@task
def load_data_mart(rows: List[Dict[str, Any]]) -> None:
    _clickhouse_execute("TRUNCATE TABLE IF EXISTS olap_db.prosthetics_data_mart")

    if not rows:
        return

    columns = [
        "customer_id", "customer_name", "customer_email", "prosthesis_model",
        "region", "purchase_date", "warranty_end_date", "warranty_status",
        "total_usage_hours", "avg_daily_usage_minutes", "total_sessions",
        "total_movements", "avg_movements_per_session", "total_errors",
        "errors_per_session", "last_active_date", "battery_health_avg",
        "most_common_movement", "data_as_of_date",
    ]

    values: List[List[Any]] = []
    for r in rows:
        values.append([r[c] for c in columns])

    _clickhouse_insert_rows("olap_db.prosthetics_data_mart", columns, values)

    count = len(rows)
    _clickhouse_execute("OPTIMIZE TABLE olap_db.prosthetics_data_mart FINAL")
    print(f"Загружено {count} записей в витрину prosthetics_data_mart")


@task
def verify_data_mart() -> None:
    resp = _clickhouse_execute("SELECT count(*) FROM olap_db.prosthetics_data_mart")
    count = int(resp.text.strip().split("\n")[0])
    if count == 0:
        raise ValueError("Витрина данных пуста после загрузки!")
    print(f"Верификация пройдена: витрина содержит {count} записей")


with DAG(
    dag_id="bionicpro_etl_crm_to_olap",
    default_args=DEFAULT_ARGS,
    description="ETL: извлечение данных из CRM и телеметрии -> загрузка в OLAP-витрину",
    schedule="0 2 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["bionicpro", "etl", "crm", "olap"],
) as dag:

    customers_data = extract_crm_customers()
    telemetry_data = extract_telemetry_aggregates()
    mart_data = build_data_mart(customers_data, telemetry_data)
    load_data_mart(mart_data) >> verify_data_mart()
