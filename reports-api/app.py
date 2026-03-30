"""
BionicPRO Reports API — отдаёт отчёты из OLAP (PostgreSQL).

Эндпоинт GET /reports возвращает подготовленную витрину fact_user_report
по заданному пользователю. Данные уже агрегированы ETL-пайплайном,
поэтому сложных вычислений в реальном времени не требуется.
"""

import os
import logging

import psycopg2
import psycopg2.extras
import requests as http_requests
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ----------------------- Config -----------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://airflow:airflow@localhost:5435/olap_data")

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


def _get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def _validate_request_auth():
    """Проверяет Bearer-токен и X-User-Id. Возвращает (user_id, error_response)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Missing or invalid Authorization header"}), 401)

    token = auth_header.split(" ", 1)[1]
    user_info = _get_user_info(token)
    if user_info is None:
        return None, (jsonify({"error": "Invalid or expired token"}), 401)

    return user_info, None


def _check_user_ownership(user_id: int):
    """Проверяет, что запрашиваемый user_id совпадает с X-User-Id. Возвращает error_response или None."""
    x_user_id = request.headers.get("X-User-Id")
    if x_user_id is not None:
        try:
            trusted_user_id = int(x_user_id)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid X-User-Id header"}), 400
        if user_id != trusted_user_id:
            return jsonify({"error": "Access denied: you can only view your own reports"}), 403
    return None


def _serialize_rows(rows):
    """Сериализует строки из БД в список словарей."""
    reports = []
    for row in rows:
        record = {}
        for key, value in row.items():
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            record[key] = value
        reports.append(record)
    return reports


def _get_available_range(user_id: int):
    """Возвращает min/max report_date для пользователя из OLAP."""
    conn = _get_db_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT MIN(report_date) AS min_date, MAX(report_date) AS max_date "
            "FROM fact_user_report WHERE user_id = %(user_id)s",
            {"user_id": user_id},
        )
        row = cur.fetchone()
    conn.close()
    return row["min_date"], row["max_date"]


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
    user_info, err = _validate_request_auth()
    if err:
        return err

    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "Query parameter 'user_id' is required"}), 400

    ownership_err = _check_user_ownership(user_id)
    if ownership_err:
        return ownership_err

    query = """
        SELECT user_id, report_date, session_count, avg_wear_time_min,
               total_gestures, avg_myosignal_quality, order_status,
               prosthesis_model, last_contact_date
        FROM fact_user_report
        WHERE user_id = %(user_id)s
    """
    params = {"user_id": user_id}

    if request.args.get("date_from"):
        query += " AND report_date >= %(date_from)s"
        params["date_from"] = request.args["date_from"]
    if request.args.get("date_to"):
        query += " AND report_date <= %(date_to)s"
        params["date_to"] = request.args["date_to"]

    query += " ORDER BY report_date DESC"

    try:
        conn = _get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.error("Database query error: %s", e)
        return jsonify({"error": "Failed to query OLAP database"}), 500

    return jsonify({
        "user_id": user_id,
        "count": len(rows),
        "reports": _serialize_rows(rows),
    })


@app.route("/reports/date-range", methods=["GET"])
def get_date_range():
    """Возвращает доступный диапазон дат отчётов для пользователя."""
    user_info, err = _validate_request_auth()
    if err:
        return err

    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "Query parameter 'user_id' is required"}), 400

    ownership_err = _check_user_ownership(user_id)
    if ownership_err:
        return ownership_err

    try:
        min_date, max_date = _get_available_range(user_id)
    except Exception as e:
        logger.error("Database query error: %s", e)
        return jsonify({"error": "Failed to query OLAP database"}), 500

    return jsonify({
        "user_id": user_id,
        "has_data": min_date is not None,
        "available_from": min_date.isoformat() if min_date else None,
        "available_to": max_date.isoformat() if max_date else None,
    })


@app.route("/reports/generate", methods=["POST"])
def generate_report():
    """Генерирует отчёт за запрошенный период.

    Если запрошенный период выходит за рамки обработанных Airflow данных,
    отчёт формируется только за доступный диапазон, а в ответе указывается,
    что данные неполные.
    """
    user_info, err = _validate_request_auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    date_from = body.get("date_from")
    date_to = body.get("date_to")

    if user_id is None:
        return jsonify({"error": "Field 'user_id' is required"}), 400
    user_id = int(user_id)

    if not date_from or not date_to:
        return jsonify({"error": "Fields 'date_from' and 'date_to' are required"}), 400

    ownership_err = _check_user_ownership(user_id)
    if ownership_err:
        return ownership_err

    try:
        min_date, max_date = _get_available_range(user_id)
    except Exception as e:
        logger.error("Database query error: %s", e)
        return jsonify({"error": "Failed to query OLAP database"}), 500

    if min_date is None:
        return jsonify({
            "user_id": user_id,
            "requested_range": {"from": date_from, "to": date_to},
            "actual_range": {"from": None, "to": None},
            "available_range": {"from": None, "to": None},
            "data_complete": False,
            "count": 0,
            "reports": [],
        })

    available_from = min_date.isoformat()
    available_to = max_date.isoformat()

    # Определяем фактический диапазон (пересечение запрошенного и доступного)
    actual_from = max(date_from, available_from)
    actual_to = min(date_to, available_to)
    data_complete = date_from >= available_from and date_to <= available_to

    if actual_from > actual_to:
        return jsonify({
            "user_id": user_id,
            "requested_range": {"from": date_from, "to": date_to},
            "actual_range": {"from": None, "to": None},
            "available_range": {"from": available_from, "to": available_to},
            "data_complete": False,
            "count": 0,
            "reports": [],
        })

    query = """
        SELECT user_id, report_date, session_count, avg_wear_time_min,
               total_gestures, avg_myosignal_quality, order_status,
               prosthesis_model, last_contact_date
        FROM fact_user_report
        WHERE user_id = %(user_id)s
          AND report_date >= %(date_from)s
          AND report_date <= %(date_to)s
        ORDER BY report_date DESC
    """
    params = {"user_id": user_id, "date_from": actual_from, "date_to": actual_to}

    try:
        conn = _get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.error("Database query error: %s", e)
        return jsonify({"error": "Failed to query OLAP database"}), 500

    return jsonify({
        "user_id": user_id,
        "requested_range": {"from": date_from, "to": date_to},
        "actual_range": {"from": actual_from, "to": actual_to},
        "available_range": {"from": available_from, "to": available_to},
        "data_complete": data_complete,
        "count": len(rows),
        "reports": _serialize_rows(rows),
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check."""
    try:
        conn = _get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "ok", "database": "connected"})
    except Exception:
        return jsonify({"status": "degraded", "database": "unavailable"}), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
