from __future__ import annotations

import os
from datetime import date
from typing import List, Optional, Literal

from fastapi import FastAPI, Query, HTTPException, Response
from pydantic import BaseModel
import clickhouse_connect


CH_HOST = os.getenv("CH_HOST", "localhost")
CH_PORT = int(os.getenv("CH_PORT", "8123"))
CH_USER = os.getenv("CH_USER", "default")
CH_PASSWORD = os.getenv("CH_PASSWORD", "")
CH_DATABASE = os.getenv("CH_DATABASE", "default")
CH_SECURE = os.getenv("CH_SECURE", "false").lower() == "true"

MART_TABLE = os.getenv("CH_MART_TABLE", "mart_user_daily_report")

app = FastAPI(title="BionicPRO Reports API", version="1.0.0")


def get_ch_client():
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD,
        database=CH_DATABASE,
        secure=CH_SECURE,
    )

class ReportRow(BaseModel):
    day: date
    customer_id: str
    prosthesis_id: str

    full_name: str
    email: str
    phone: str
    country: str
    city: str
    contract_id: str

    samples_count: int
    active_seconds: int
    movements_count: int
    errors_count: int
    avg_battery: float
    max_load: float


class ReportResponse(BaseModel):
    customer_id: str
    date_from: date
    date_to: date
    rows: List[ReportRow]


@app.get("/reports", response_model=ReportResponse)
def get_report(
    customer_id: str = Query(..., description="Идентификатор клиента (как в витрине mart_user_daily_report)"),
    date_from: date = Query(..., description="Начало периода (включительно)"),
    date_to: date = Query(..., description="Конец периода (включительно)"),
    format: Literal["json", "csv"] = Query("json", description="Формат ответа"),
    limit: int = Query(366, ge=1, le=2000, description="Максимум строк (обычно по дням)"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
):
    if date_to < date_from:
        raise HTTPException(status_code=400, detail="date_to must be >= date_from")

    ch = get_ch_client()

    query = f"""
    SELECT
      day,
      customer_id,
      prosthesis_id,
      full_name,
      email,
      phone,
      country,
      city,
      contract_id,
      samples_count,
      active_seconds,
      movements_count,
      errors_count,
      avg_battery,
      max_load
    FROM {MART_TABLE}
    WHERE customer_id = %(customer_id)s
      AND day >= toDate(%(date_from)s)
      AND day <= toDate(%(date_to)s)
    ORDER BY day ASC
    LIMIT %(limit)s OFFSET %(offset)s
    """

    result = ch.query(
        query,
        parameters={
            "customer_id": customer_id,
            "date_from": str(date_from),
            "date_to": str(date_to),
            "limit": limit,
            "offset": offset,
        },
    )

    cols = result.column_names
    rows = result.result_rows

    report_rows = [dict(zip(cols, r)) for r in rows]

    if format == "csv":
        header = ",".join(cols)
        lines = [header]
        for r in rows:
            out = []
            for v in r:
                s = "" if v is None else str(v)
                if '"' in s:
                    s = s.replace('"', '""')
                if "," in s or "\n" in s or '"' in s:
                    s = f'"{s}"'
                out.append(s)
            lines.append(",".join(out))
        csv_body = "\n".join(lines) + "\n"

        filename = f"report_{customer_id}_{date_from}_{date_to}.csv"
        return Response(
            content=csv_body,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # JSON
    return ReportResponse(
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        rows=[ReportRow(**r) for r in report_rows],
    )


@app.get("/health")
def health():
    try:
        ch = get_ch_client()
        v = ch.query("SELECT 1").result_rows[0][0]
        return {"status": "ok", "clickhouse": bool(v == 1)}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}
