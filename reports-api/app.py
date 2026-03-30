"""
BionicPRO Reports API — отдаёт отчёты из OLAP (ClickHouse).

Эндпоинт GET /reports возвращает подготовленную витрину fact_user_report
по заданному пользователю. Данные уже агрегированы ETL-пайплайном,
поэтому сложных вычислений в реальном времени не требуется.
"""

import os
import logging

import requests as http_requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from clickhouse_driver import Client as ClickHouseClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ----------------------- Config -----------------------

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_DB = os.environ.get("CLICKHOUSE_DB", "default")

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "reports-realm")


# ----------------------- Auth -------------------------

def _get_user_info(access_token: str) -> dict | None:
    """Валидация токена через Keycloak userinfo endpoint."""
    url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
    try:
        resp = http_requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
    except http_requests.RequestException as e:
        logger.error("Keycloak userinfo error: %s", e)
    return None


def _get_clickhouse_client() -> ClickHouseClient:
    return ClickHouseClient(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB,
    )


# ----------------------- Routes -----------------------

@app.route("/reports", methods=["GET"])
def get_reports():
    """Возвращает отчёт из витрины fact_user_report.

    Query-параметры:
      - user_id (int, обязательный) — ID пользователя
      - date_from (str, опционально) — начало периода (YYYY-MM-DD)
      - date_to   (str, опционально) — конец периода (YYYY-MM-DD)

    Авторизация: Bearer-токен (проксируется из bionicpro-auth).
    """
    # --- Авторизация ---
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ", 1)[1]
    user_info = _get_user_info(token)
    if user_info is None:
        return jsonify({"error": "Invalid or expired token"}), 401

    # --- Параметры запроса ---
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "Query parameter 'user_id' is required"}), 400

    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    # --- Запрос к ClickHouse ---
    query = """
        SELECT
            user_id,
            report_date,
            session_count,
            avg_wear_time_min,
            total_gestures,
            avg_myosignal_quality,
            order_status,
            prosthesis_model,
            last_contact_date
        FROM fact_user_report
        WHERE user_id = %(user_id)s
    """
    params = {"user_id": user_id}

    if date_from:
        query += " AND report_date >= %(date_from)s"
        params["date_from"] = date_from
    if date_to:
        query += " AND report_date <= %(date_to)s"
        params["date_to"] = date_to

    query += " ORDER BY report_date DESC"

    try:
        ch = _get_clickhouse_client()
        rows = ch.execute(query, params, with_column_types=True)
        data, columns = rows
        column_names = [col[0] for col in columns]
    except Exception as e:
        logger.error("ClickHouse query error: %s", e)
        return jsonify({"error": "Failed to query OLAP database"}), 500

    # --- Формирование ответа ---
    reports = []
    for row in data:
        record = {}
        for i, name in enumerate(column_names):
            value = row[i]
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            record[name] = value
        reports.append(record)

    return jsonify({
        "user_id": user_id,
        "count": len(reports),
        "reports": reports,
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check."""
    try:
        ch = _get_clickhouse_client()
        ch.execute("SELECT 1")
        return jsonify({"status": "ok", "clickhouse": "connected"})
    except Exception:
        return jsonify({"status": "degraded", "clickhouse": "unavailable"}), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
