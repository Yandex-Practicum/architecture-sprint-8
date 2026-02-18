import logging
from typing import List, Optional
from datetime import datetime
import clickhouse_connect
from clickhouse_connect.driver import Client

from .config import settings
from .models import ReportResponse

logger = logging.getLogger(__name__)


class ClickHouseClient:
    
    def __init__(self):
        self.client: Optional[Client] = None
        self._connect()
    
    def _connect(self):
        try:
            self.client = clickhouse_connect.get_client(
                host=settings.CLICKHOUSE_HOST,
                port=settings.CLICKHOUSE_PORT,
                username=settings.CLICKHOUSE_USER,
                password=settings.CLICKHOUSE_PASSWORD,
                database=settings.CLICKHOUSE_DATABASE
            )
            logger.info(f"Connected to ClickHouse at {settings.CLICKHOUSE_HOST}:{settings.CLICKHOUSE_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {e}")
            raise
    
    def check_connection(self) -> bool:
        try:
            result = self.client.query("SELECT 1")
            return result.result_rows[0][0] == 1
        except Exception as e:
            logger.error(f"ClickHouse connection check failed: {e}")
            return False
    
    def get_report(self, user_id: int, period: str) -> Optional[ReportResponse]:
        period_date = datetime.strptime(period, "%Y-%m").date()
        period_yyyymm = int(period.replace("-", ""))
        
        query = f"""
            SELECT 
                user_id,
                device_id,
                period_month,
                full_name,
                email,
                country,
                device_type,
                total_signals,
                myo_signals_count,
                battery_checks_count,
                actuator_events_count,
                total_actions,
                most_frequent_action,
                action_frequency,
                avg_processing_time_ms,
                min_processing_time_ms,
                max_processing_time_ms,
                device_status,
                warranty_until,
                report_generated_at,
                data_freshness_date
            FROM reports_mart
            WHERE user_id = {user_id}
              AND toYYYYMM(period_month) = {period_yyyymm}
            LIMIT 1
        """
        
        try:
            result = self.client.query(query)
            
            if not result.result_rows:
                logger.info(f"No report found for user_id={user_id}, period={period}")
                return None
            
            row = result.result_rows[0]
            
            return ReportResponse(
                user_id=row[0],
                device_id=row[1],
                period_month=row[2],
                full_name=row[3],
                email=row[4],
                country=row[5],
                device_type=row[6],
                total_signals=row[7],
                myo_signals_count=row[8],
                battery_checks_count=row[9],
                actuator_events_count=row[10],
                total_actions=row[11],
                most_frequent_action=row[12],
                action_frequency=row[13],
                avg_processing_time_ms=row[14],
                min_processing_time_ms=row[15],
                max_processing_time_ms=row[16],
                device_status=row[17],
                warranty_until=row[18],
                report_generated_at=row[19],
                data_freshness_date=row[20]
            )
            
        except Exception as e:
            logger.error(f"Error fetching report: {e}")
            raise
    
    def get_user_reports(self, user_id: int, limit: int = 10) -> List[ReportResponse]:
        query = f"""
            SELECT 
                user_id,
                device_id,
                period_month,
                full_name,
                email,
                country,
                device_type,
                total_signals,
                myo_signals_count,
                battery_checks_count,
                actuator_events_count,
                total_actions,
                most_frequent_action,
                action_frequency,
                avg_processing_time_ms,
                min_processing_time_ms,
                max_processing_time_ms,
                device_status,
                warranty_until,
                report_generated_at,
                data_freshness_date
            FROM reports_mart
            WHERE user_id = {user_id}
            ORDER BY period_month DESC
            LIMIT {limit}
        """
        
        try:
            result = self.client.query(query)
            
            reports = []
            for row in result.result_rows:
                reports.append(ReportResponse(
                    user_id=row[0],
                    device_id=row[1],
                    period_month=row[2],
                    full_name=row[3],
                    email=row[4],
                    country=row[5],
                    device_type=row[6],
                    total_signals=row[7],
                    myo_signals_count=row[8],
                    battery_checks_count=row[9],
                    actuator_events_count=row[10],
                    total_actions=row[11],
                    most_frequent_action=row[12],
                    action_frequency=row[13],
                    avg_processing_time_ms=row[14],
                    min_processing_time_ms=row[15],
                    max_processing_time_ms=row[16],
                    device_status=row[17],
                    warranty_until=row[18],
                    report_generated_at=row[19],
                    data_freshness_date=row[20]
                ))
            
            return reports
            
        except Exception as e:
            logger.error(f"Error fetching user reports: {e}")
            raise
    
    def close(self):
        if self.client:
            self.client.close()
            logger.info("ClickHouse connection closed")


clickhouse_client = ClickHouseClient()
