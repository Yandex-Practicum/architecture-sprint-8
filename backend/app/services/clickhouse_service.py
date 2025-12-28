"""Сервис для работы с ClickHouse."""

import os
import logging
from typing import List, Optional
from datetime import date
import clickhouse_connect
from clickhouse_connect.driver.client import Client

from app.models.report import ReportData

logger = logging.getLogger(__name__)


class ClickHouseService:
    """Сервис для получения отчётов из ClickHouse."""
    
    def __init__(self):
        self.host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
        self.port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
        self.database = os.getenv('CLICKHOUSE_DATABASE', 'bionicpro')
        self._client: Optional[Client] = None
    
    def _get_client(self) -> Client:
        """Получение клиента ClickHouse."""
        if self._client is None:
            self._client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                database=self.database
            )
        return self._client
    
    def get_reports_by_user(
        self, 
        user_id: str, 
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 30
    ) -> List[ReportData]:
        """
        Получение отчётов по пользователю.
        
        Args:
            user_id: ID пользователя
            date_from: Начальная дата (опционально)
            date_to: Конечная дата (опционально)
            limit: Максимальное количество записей
            
        Returns:
            Список отчётов
        """
        client = self._get_client()
        
        # Базовый запрос с фильтрацией по user_id
        query = '''
            SELECT 
                user_id,
                username,
                email,
                first_name,
                last_name,
                prosthetic_model,
                report_date,
                total_usage_hours,
                movement_count,
                avg_response_time_ms,
                battery_cycles,
                calibration_count,
                last_sync_at,
                etl_processed_at
            FROM reports_mart
            WHERE user_id = {user_id:String}
        '''
        
        params = {'user_id': user_id}
        
        # Добавление фильтров по дате
        if date_from:
            query += ' AND report_date >= {date_from:Date}'
            params['date_from'] = date_from.isoformat()
        
        if date_to:
            query += ' AND report_date <= {date_to:Date}'
            params['date_to'] = date_to.isoformat()
        
        # Сортировка и лимит
        query += ' ORDER BY report_date DESC LIMIT {limit:UInt32}'
        params['limit'] = limit
        
        try:
            result = client.query(query, parameters=params)
            
            reports = []
            for row in result.result_rows:
                reports.append(ReportData(
                    user_id=row[0],
                    username=row[1],
                    email=row[2],
                    first_name=row[3],
                    last_name=row[4],
                    prosthetic_model=row[5],
                    report_date=row[6],
                    total_usage_hours=row[7],
                    movement_count=row[8],
                    avg_response_time_ms=row[9],
                    battery_cycles=row[10],
                    calibration_count=row[11],
                    last_sync_at=row[12],
                    etl_processed_at=row[13]
                ))
            
            logger.info(f"Retrieved {len(reports)} reports for user {user_id}")
            return reports
            
        except Exception as e:
            logger.error(f"Error fetching reports for user {user_id}: {e}")
            raise
    
    def get_latest_etl_date(self) -> Optional[date]:
        """Получение даты последней обработки ETL."""
        client = self._get_client()
        
        try:
            result = client.query('''
                SELECT MAX(report_date) as latest_date
                FROM reports_mart
            ''')
            
            if result.result_rows and result.result_rows[0][0]:
                return result.result_rows[0][0]
            return None
            
        except Exception as e:
            logger.error(f"Error fetching latest ETL date: {e}")
            return None
    
    def check_data_availability(self, user_id: str, report_date: date) -> bool:
        """Проверка доступности данных за указанную дату."""
        client = self._get_client()
        
        try:
            result = client.query('''
                SELECT count(*) 
                FROM reports_mart 
                WHERE user_id = {user_id:String} 
                AND report_date = {report_date:Date}
            ''', parameters={'user_id': user_id, 'report_date': report_date.isoformat()})
            
            count = result.result_rows[0][0] if result.result_rows else 0
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking data availability: {e}")
            return False


# Singleton instance
clickhouse_service = ClickHouseService()

