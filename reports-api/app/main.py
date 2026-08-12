from fastapi import Depends, FastAPI, HTTPException

from .auth import get_current_username
from .clickhouse_client import get_latest_report
from .redis_cache import get_cached_pointer, set_cached_pointer
from .s3_client import ensure_bucket, get_cached_report_url, object_key_for, store_report

app = FastAPI(title="reports-api")


@app.on_event("startup")
async def startup():
    ensure_bucket()


@app.get("/reports")
async def get_my_report(username: str = Depends(get_current_username)):
    # customer_id всегда берётся из проверенного токена, а не из параметра,
    # переданного клиентом, поэтому пользователь может получить доступ
    # только к собственному отчёту.

    # 1. Указатель в Redis: полностью пропускает ClickHouse при повторных
    #    запросах в пределах TTL - именно это убирает повторную нагрузку
    #    на OLAP, о которой идёт речь в задании.
    pointer = get_cached_pointer(username)
    if pointer:
        cached_url = get_cached_report_url(pointer["object_key"])
        if cached_url:
            return {"url": cached_url, "cached": True}

    # 2. Указателя нет/истёк, либо объект пропал из S3: ищем последний
    #    обработанный ETL отчёт (дешёвый точечный запрос по индексу,
    #    никогда не вычисление агрегатов на лету).
    report = get_latest_report(username)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No report has been generated for the current processed period yet",
        )

    object_key = object_key_for(username, report["report_generated_at"])
    set_cached_pointer(username, report["report_generated_at"], object_key)

    # 3. Кэш объекта в S3/CDN: перегенерируем JSON только если его ещё нет
    #    в объектном хранилище для этого конкретного обработанного периода.
    cached_url = get_cached_report_url(object_key)
    if cached_url:
        return {"url": cached_url, "cached": True}

    url = store_report(object_key, report)
    return {"url": url, "cached": False}


@app.get("/health")
async def health():
    return {"status": "ok"}
