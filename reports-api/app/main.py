"""reports-api — сервис отчётов BionicPRO."""
import clickhouse_connect
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import s3_store
from .config import settings

app = FastAPI(title="reports-api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    s3_store.ensure_bucket()


def _clickhouse():
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
    )


async def _validate_session(request: Request) -> dict:
    """bionicpro-auth при каждой валидации ротирует session_id (см. new_session_id)."""
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.auth_service_url}/auth/validate",
            cookies={settings.session_cookie_name: session_id},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    return resp.json()


def _set_rotated_cookie(response: JSONResponse, new_session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=new_session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# Дешёвый запрос версии витрины: проверка готовности и свежести кеша без
# выгрузки всего отчёта.
_VERSION_SQL = {
    "airflow": """
        SELECT max(processed_at)
        FROM reports.user_report
        WHERE username = {username:String}
    """,
    "realtime": """
        SELECT max(t.ts)
        FROM reports.telemetry_raw AS t
        INNER JOIN
        (
            SELECT id, argMax(username, _synced_at) AS username
            FROM reports.clients_dim
            GROUP BY id
        ) AS c ON c.id = t.client_id
        WHERE c.username = {username:String}
    """,
}

# Обе ветки должны возвращать колонки в одном порядке: _generate_report читает
# строки по позициям.
_REPORT_SQL = {
    "airflow": """
        SELECT
            username,
            any(full_name)        AS full_name,
            any(prosthesis_model) AS prosthesis_model,
            period_date,
            avg_response_time_ms,
            max_response_time_ms,
            min_battery_level,
            total_movements,
            samples_count
        FROM reports.user_report
        WHERE username = {username:String}
        GROUP BY username, period_date, avg_response_time_ms,
                 max_response_time_ms, min_battery_level,
                 total_movements, samples_count
        ORDER BY period_date
    """,
    "realtime": """
        SELECT
            c.username AS username,
            any(c.full_name) AS full_name,
            any(c.prosthesis_model) AS prosthesis_model,
            r.period_date AS period_date,
            avgMerge(r.avg_response_state) AS avg_response_time_ms,
            maxMerge(r.max_response_state) AS max_response_time_ms,
            minMerge(r.min_battery_state)  AS min_battery_level,
            sumMerge(r.sum_moves_state)    AS total_movements,
            countMerge(r.samples_state)    AS samples_count
        FROM reports.user_report_rt AS r
        INNER JOIN
        (
            SELECT id,
                   argMax(username, _synced_at) AS username,
                   argMax(full_name, _synced_at) AS full_name,
                   argMax(prosthesis_model, _synced_at) AS prosthesis_model
            FROM reports.clients_dim
            GROUP BY id
        ) AS c ON c.id = r.client_id
        WHERE c.username = {username:String}
        GROUP BY c.username, r.period_date
        ORDER BY r.period_date
    """,
}


def _report_version(client, username: str) -> int | None:
    result = client.query(
        _VERSION_SQL[settings.report_mart], parameters={"username": username}
    )
    if not result.result_rows or result.result_rows[0][0] is None:
        return None
    return int(result.result_rows[0][0].timestamp())


def _generate_report(client, username: str) -> dict:
    result = client.query(
        _REPORT_SQL[settings.report_mart], parameters={"username": username}
    )
    periods = [
        {
            "period_date": str(row[3]),
            "avg_response_time_ms": round(float(row[4]), 1),
            "max_response_time_ms": int(row[5]),
            "min_battery_level": int(row[6]),
            "total_movements": int(row[7]),
            "samples_count": int(row[8]),
        }
        for row in result.result_rows
    ]
    return {
        "username": username,
        "full_name": result.result_rows[0][1] if result.result_rows else "",
        "prosthesis_model": result.result_rows[0][2] if result.result_rows else "",
        "periods": periods,
    }


@app.get("/reports")
async def get_report(request: Request):
    """username берётся только из сессии — доступ строго к своим данным.
    Полный отчёт из OLAP собирается лишь при cache-miss; при попадании в кеш S3
    база не трогается.
    """
    identity = await _validate_session(request)
    username = identity.get("username")
    if not username:
        raise HTTPException(status_code=403, detail="No user identity")

    client = _clickhouse()
    version = _report_version(client, username)
    if version is None:
        raise HTTPException(
            status_code=404, detail="Report is not ready yet for this user"
        )

    object_key = f"{username}/{version}.json"
    cached = s3_store.exists(object_key)
    if not cached:
        report = _generate_report(client, username)
        s3_store.put_json(object_key, report)

    report_url = f"{settings.cdn_base_url}/{settings.s3_bucket}/{object_key}"
    response = JSONResponse(
        {
            "report_url": report_url,
            "version": version,
            "source": "s3-cache" if cached else "generated",
        }
    )
    _set_rotated_cookie(response, identity["new_session_id"])
    return response
