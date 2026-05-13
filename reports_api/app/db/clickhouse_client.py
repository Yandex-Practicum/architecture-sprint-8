import requests
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ClickHouseHTTPClient:
    def __init__(self, host: str = "clickhouse", port: int = 8123, user: str = "default",
                 password: str = "", database: str = "reports"):
        self.base_url = f"http://{host}:{port}"
        self.database = database
        self.user = user
        self.password = password
        logger.info(f"ClickHouse HTTP client initialized: {self.base_url}, user={user}")

    def execute(self, query: str, params: Optional[Dict] = None) -> List[List]:
        """Execute query using HTTP interface"""
        # URL с параметрами аутентификации
        url = f"{self.base_url}/?database={self.database}&default_format=JSON&user={self.user}"

        if self.password:
            url += f"&password={self.password}"

        # Простая подстановка параметров
        if params:
            for key, value in params.items():
                if isinstance(value, str):
                    query = query.replace(f"%({key})s", f"'{value}'")
                else:
                    query = query.replace(f"%({key})s", str(value))

        logger.debug(f"Executing query: {query[:200]}...")

        try:
            response = requests.post(
                url,
                data=query.encode("utf-8"),
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"ClickHouse error (status {response.status_code}): {response.text}")
                raise Exception(f"ClickHouse error: {response.text}")

            if not response.text.strip():
                return []

            data = response.json()

            # Преобразуем в формат, совместимый с clickhouse_driver
            if "data" in data and data["data"]:
                if "meta" in data:
                    columns = [col["name"] for col in data["meta"]]
                    result = []
                    for row in data["data"]:
                        result.append([row.get(col) for col in columns])
                    return result
                elif isinstance(data["data"], list):
                    return data["data"]

            return []

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            raise Exception(f"HTTP request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            if "response" in locals():
                logger.error(f"Response text: {response.text[:200]}")
            raise Exception(f"Invalid response from ClickHouse: {str(e)}")

    def close(self):
        """Close connection (no-op for HTTP client)"""
        pass


def get_clickhouse_client():
    """Get ClickHouse HTTP client"""
    logger.info("Creating ClickHouse HTTP client")
    return ClickHouseHTTPClient(
        host="clickhouse",
        port=8123,
        user="default",
        password="",
        database="reports",
    )
