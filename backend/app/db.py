import clickhouse_connect
from clickhouse_connect.driver.client import Client

from app.settings import settings


def get_clickhouse_client() -> Client:
    """
    Создает и кеширует подключение к ClickHouse.
    """
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_db,
    )
