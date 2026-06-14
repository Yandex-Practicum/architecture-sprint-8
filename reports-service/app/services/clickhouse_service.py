"""
ClickHouse service for querying reports data from OLAP database.
"""

import logging
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from clickhouse_driver import Client
from clickhouse_driver.errors import Error as ClickHouseError

from app.config import get_settings

logger = logging.getLogger(__name__)


class ClickHouseService:
    """Service for interacting with ClickHouse OLAP database."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[Client] = None

    def _get_client(self) -> Client:
        """Get or create ClickHouse client connection."""
        if self._client is None:
            self._client = Client(
                host=self.settings.clickhouse_host,
                port=self.settings.clickhouse_port,
                user=self.settings.clickhouse_user,
                password=self.settings.clickhouse_password,
                database=self.settings.clickhouse_database,
            )
        return self._client

    def close(self):
        """Close the connection."""
        if self._client:
            self._client.disconnect()
            self._client = None

    def get_reports_list(
        self,
        user_id: str,
        limit: int = 30,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get list of available reports for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of reports to return
            offset: Offset for pagination

        Returns:
            Dictionary with user info and list of report summaries
        """
        client = self._get_client()

        # Get user info and report count
        info_query = """
            SELECT
                any(customer_name) AS customer_name,
                any(prosthesis_model) AS prosthesis_model,
                count(DISTINCT report_date) AS total_reports,
                min(report_date) AS first_date,
                max(report_date) AS last_date
            FROM user_prosthesis_stats
            WHERE user_id = %(user_id)s
        """

        info_result = client.execute(info_query, {"user_id": user_id})

        if not info_result or not info_result[0][0]:
            return None

        customer_name, prosthesis_model, total_reports, first_date, last_date = info_result[0]

        # Get report summaries
        # Note: LIMIT and OFFSET cannot be parameterized in clickhouse-driver
        # Using f-string is safe here since limit/offset are always integers
        reports_query = f"""
            SELECT
                report_date,
                sum(movements_count) AS total_movements,
                sum(error_count) AS total_errors,
                count(DISTINCT report_hour) AS active_hours
            FROM user_prosthesis_stats
            WHERE user_id = %(user_id)s
            GROUP BY report_date
            ORDER BY report_date DESC
            LIMIT {limit} OFFSET {offset}
        """

        reports_result = client.execute(
            reports_query,
            {"user_id": user_id}
        )

        reports = [
            {
                "report_date": row[0],
                "total_movements": row[1],
                "total_errors": row[2],
                "active_hours": row[3],
            }
            for row in reports_result
        ]

        return {
            "user_id": user_id,
            "customer_name": customer_name,
            "prosthesis_model": prosthesis_model,
            "total_reports": total_reports,
            "date_range": {
                "first_date": str(first_date) if first_date else None,
                "last_date": str(last_date) if last_date else None,
            },
            "reports": reports,
        }

    def get_daily_report(
        self,
        user_id: str,
        report_date: date,
        include_hourly: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed daily report for a user.

        Args:
            user_id: User identifier
            report_date: Date of the report
            include_hourly: Whether to include hourly breakdown

        Returns:
            Dictionary with daily report data or None if not found
        """
        client = self._get_client()

        # Get daily aggregates
        daily_query = """
            SELECT
                report_date,
                any(customer_name) AS customer_name,
                any(prosthesis_id) AS prosthesis_id,
                any(prosthesis_model) AS prosthesis_model,
                any(prosthesis_serial) AS prosthesis_serial,
                any(customer_region) AS customer_region,
                sum(movements_count) AS total_movements,
                sum(successful_movements) AS total_successful,
                if(sum(movements_count) > 0,
                   round(sum(successful_movements) / sum(movements_count) * 100, 2),
                   0) AS daily_success_rate,
                round(avg(avg_response_time), 2) AS avg_response_time,
                round(avg(avg_battery_level), 1) AS avg_battery_level,
                min(min_battery_level) AS min_battery_level,
                max(max_actuator_temp) AS max_actuator_temp,
                sum(error_count) AS total_errors,
                count(DISTINCT report_hour) AS active_hours
            FROM user_prosthesis_stats
            WHERE user_id = %(user_id)s
              AND report_date = %(report_date)s
            GROUP BY report_date
        """

        daily_result = client.execute(
            daily_query,
            {"user_id": user_id, "report_date": report_date}
        )

        if not daily_result:
            return None

        row = daily_result[0]
        report = {
            "report_date": row[0],
            "user_id": user_id,
            "customer_name": row[1],
            "prosthesis_id": row[2],
            "prosthesis_model": row[3],
            "prosthesis_serial": row[4],
            "customer_region": row[5],
            "total_movements": row[6],
            "total_successful": row[7],
            "daily_success_rate": float(row[8]),
            "avg_response_time": float(row[9]),
            "avg_battery_level": float(row[10]),
            "min_battery_level": row[11],
            "max_actuator_temp": float(row[12]),
            "total_errors": row[13],
            "active_hours": row[14],
        }

        # Get hourly breakdown if requested
        if include_hourly:
            hourly_query = """
                SELECT
                    report_hour,
                    movements_count,
                    successful_movements,
                    success_rate,
                    avg_response_time,
                    avg_battery_level,
                    error_count
                FROM user_prosthesis_stats
                WHERE user_id = %(user_id)s
                  AND report_date = %(report_date)s
                ORDER BY report_hour
            """

            hourly_result = client.execute(
                hourly_query,
                {"user_id": user_id, "report_date": report_date}
            )

            report["hourly_stats"] = [
                {
                    "hour": row[0],
                    "movements_count": row[1],
                    "successful_movements": row[2],
                    "success_rate": float(row[3]) if row[3] else 0,
                    "avg_response_time": float(row[4]) if row[4] else 0,
                    "avg_battery_level": float(row[5]) if row[5] else 0,
                    "error_count": row[6],
                }
                for row in hourly_result
            ]

        return report

    def get_user_summary(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get overall summary for a user across all time.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with user summary or None if not found
        """
        client = self._get_client()

        query = """
            SELECT
                any(customer_name) AS customer_name,
                any(prosthesis_model) AS prosthesis_model,
                any(prosthesis_serial) AS prosthesis_serial,
                any(customer_region) AS customer_region,
                min(report_date) AS first_activity_date,
                max(report_date) AS last_activity_date,
                dateDiff('day', min(report_date), max(report_date)) + 1 AS total_days,
                count(DISTINCT report_date) AS active_days,
                sum(movements_count) AS total_movements,
                sum(successful_movements) AS total_successful,
                if(sum(movements_count) > 0,
                   round(sum(successful_movements) / sum(movements_count) * 100, 2),
                   0) AS overall_success_rate,
                round(avg(avg_response_time), 2) AS avg_response_time,
                round(avg(avg_battery_level), 1) AS avg_battery_level,
                sum(error_count) AS total_errors,
                round(sum(error_count) / count(DISTINCT report_date), 2) AS avg_errors_per_day
            FROM user_prosthesis_stats
            WHERE user_id = %(user_id)s
        """

        result = client.execute(query, {"user_id": user_id})

        if not result or not result[0][0]:
            return None

        row = result[0]
        return {
            "user_id": user_id,
            "customer_name": row[0],
            "prosthesis_model": row[1],
            "prosthesis_serial": row[2],
            "customer_region": row[3],
            "first_activity_date": row[4],
            "last_activity_date": row[5],
            "total_days": row[6],
            "active_days": row[7],
            "total_movements": row[8],
            "total_successful": row[9],
            "overall_success_rate": float(row[10]),
            "avg_response_time": float(row[11]),
            "avg_battery_level": float(row[12]),
            "total_errors": row[13],
            "avg_errors_per_day": float(row[14]),
        }

    def health_check(self) -> bool:
        """Check if ClickHouse is available."""
        try:
            client = self._get_client()
            result = client.execute("SELECT 1")
            return result[0][0] == 1
        except ClickHouseError as e:
            logger.error(f"ClickHouse health check failed: {e}")
            return False

    def get_cdc_status(self) -> Dict[str, Any]:
        """
        Get CDC (Change Data Capture) pipeline status.

        Checks if Debezium CDC data is flowing into ClickHouse.
        Returns counts and last update times for CDC tables.

        Задание 4: Проверка состояния CDC.
        """
        client = self._get_client()

        try:
            query = """
                SELECT
                    'customers' AS entity,
                    count() AS total,
                    countIf(_deleted = 0) AS active
                FROM crm_customers FINAL

                UNION ALL

                SELECT
                    'prostheses' AS entity,
                    count() AS total,
                    countIf(_deleted = 0) AS active
                FROM crm_prostheses FINAL

                UNION ALL

                SELECT
                    'models' AS entity,
                    count() AS total,
                    countIf(_deleted = 0) AS active
                FROM crm_prosthesis_models FINAL
            """

            result = client.execute(query)

            cdc_data = {}
            for row in result:
                entity, total, active = row
                cdc_data[entity] = {"total": total, "active": active}

            # Проверяем готовность витрины
            mart_query = """
                SELECT count() FROM cdc_customer_data FINAL
            """
            mart_result = client.execute(mart_query)
            mart_count = mart_result[0][0] if mart_result else 0

            return {
                "cdc_tables": cdc_data,
                "mart_ready": mart_count > 0,
                "mart_records": mart_count,
                "status": "ready" if mart_count > 0 else "initializing",
            }

        except ClickHouseError as e:
            logger.error(f"CDC status check failed: {e}")
            return {
                "cdc_tables": {},
                "mart_ready": False,
                "mart_records": 0,
                "status": "error",
                "error": str(e),
            }


# Singleton instance
_clickhouse_service: Optional[ClickHouseService] = None


def get_clickhouse_service() -> ClickHouseService:
    """Get singleton ClickHouse service instance."""
    global _clickhouse_service
    if _clickhouse_service is None:
        _clickhouse_service = ClickHouseService()
    return _clickhouse_service
