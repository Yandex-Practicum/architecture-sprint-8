import os
from clickhouse_driver import Client

def get_clickhouse_client() -> Client:
    return Client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        database="default"
    )
