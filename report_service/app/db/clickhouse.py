# app/db/clickhouse.py
from clickhouse_driver import Client
import os
import logging

logger = logging.getLogger(__name__)

# Загружаем настройки напрямую из окружения
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "reports")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")


class ClickHouseClient:
    def __init__(self):
        self.client = Client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE
        )

    def get_user_reports(self, user_id: str, start_date=None, end_date=None):
        """Получить отчёты пользователя за период"""
        try:
            query = """
            SELECT 
                user_id,
                prosthetic_id,
                report_date,
                total_usage_minutes,
                avg_response_time_ms,
                battery_cycles,
                movements_count,
                successful_movements,
                failed_movements,
                calibration_count,
                data_volume_mb
            FROM reports.report_fact
            WHERE user_id = %(user_id)s
            """
            params = {'user_id': user_id}

            if start_date:
                query += " AND report_date >= %(start_date)s"
                params['start_date'] = start_date
            if end_date:
                query += " AND report_date <= %(end_date)s"
                params['end_date'] = end_date

            query += " ORDER BY report_date DESC"

            result = self.client.execute(query, params)

            # Преобразуем в список словарей
            columns = [
                'user_id', 'prosthetic_id', 'report_date',
                'total_usage_minutes', 'avg_response_time_ms', 'battery_cycles',
                'movements_count', 'successful_movements', 'failed_movements',
                'calibration_count', 'data_volume_mb'
            ]

            reports = []
            for row in result:
                report = dict(zip(columns, row))
                reports.append(report)

            return reports

        except Exception as e:
            logger.error(f"Error fetching reports: {e}")
            raise


# Создаём глобальный экземпляр
clickhouse_client = ClickHouseClient()