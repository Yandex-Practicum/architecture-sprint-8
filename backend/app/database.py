"""
Модуль для работы с ClickHouse
"""
import os
from clickhouse_driver import Client
from typing import Optional

# Параметры подключения к ClickHouse
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "bionicpro_reports")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_password")

# Глобальный клиент (singleton)
_clickhouse_client: Optional[Client] = None


def get_clickhouse_client() -> Client:
    """
    Получить клиент ClickHouse (singleton)
    
    Returns:
        Client: Клиент ClickHouse
    """
    global _clickhouse_client
    
    if _clickhouse_client is None:
        _clickhouse_client = Client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            database=CLICKHOUSE_DATABASE,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD
        )
    
    return _clickhouse_client


def close_clickhouse_client():
    """Закрыть соединение с ClickHouse"""
    global _clickhouse_client
    if _clickhouse_client:
        _clickhouse_client.disconnect()
        _clickhouse_client = None
