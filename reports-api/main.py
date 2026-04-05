import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

import clickhouse_connect
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_user: str = "clickhouse_user"
    clickhouse_password: str = "clickhouse_password"
    clickhouse_database: str = "bionicpro"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

SQL_REPORTS = """
SELECT
    period_date,
    avg_temperature,
    avg_pulse,
    plan_code,
    data_watermark_date
FROM bionicpro.reports_mart
WHERE user_id = {uid:String}
ORDER BY period_date, mart_loaded_at
"""


class PeriodRow(BaseModel):
    period_date: date
    avg_temperature: float | None
    avg_pulse: float | None
    plan_code: str
    data_watermark_date: date


class ReportResponse(BaseModel):
    user_id: str
    periods: list[PeriodRow]


class ClickHouseUnavailableError(Exception):
    """Raised when the reports query against ClickHouse fails."""


def _fetch_periods(client, user_id: str) -> list[PeriodRow]:
    try:
        result = client.query(SQL_REPORTS, parameters={"uid": user_id})
    except Exception as e:
        logger.exception("ClickHouse query failed for user_id=%s", user_id)
        raise ClickHouseUnavailableError from e
    rows: list[PeriodRow] = []
    for tup in result.result_rows:
        rows.append(
            PeriodRow(
                period_date=tup[0],
                avg_temperature=tup[1],
                avg_pulse=tup[2],
                plan_code=tup[3],
                data_watermark_date=tup[4],
            )
        )
    return rows


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.clickhouse = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
    )
    try:
        yield
    finally:
        app.state.clickhouse.close()


app = FastAPI(title="bionicpro-reports-api", lifespan=lifespan)


@app.get("/reports", response_model=ReportResponse)
def reports(
    request: Request,
    x_user_id: Annotated[str, Header(alias="X-User-Id")],
):
    if not x_user_id.strip():
        raise HTTPException(status_code=422, detail="X-User-Id must not be empty")

    client = request.app.state.clickhouse
    try:
        periods = _fetch_periods(client, x_user_id)
    except ClickHouseUnavailableError as e:
        raise HTTPException(
            status_code=503, detail="reports data source unavailable"
        ) from e.__cause__

    return ReportResponse(user_id=x_user_id, periods=periods)
