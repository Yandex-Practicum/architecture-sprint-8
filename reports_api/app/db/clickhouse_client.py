from clickhouse_driver import Client
import os

def get_clickhouse_client():
    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.getenv("CLICKHOUSE_PORT", 9000)),
        user="default",
        password="",
        database="reports"
    )
