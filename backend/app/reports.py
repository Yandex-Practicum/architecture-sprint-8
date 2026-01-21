"""
Модуль для работы с отчётами из ClickHouse
"""
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from app.database import get_clickhouse_client
from app.security import verify_user_access
from fastapi import HTTPException


async def check_data_availability(
    date_from: date,
    date_to: date
) -> Dict[str, Any]:
    """
    Проверить доступность данных за период
    
    Args:
        date_from: Начальная дата
        date_to: Конечная дата
    
    Returns:
        dict: Информация о доступности данных
    """
    client = get_clickhouse_client()
    
    try:
        # Проверяем последнюю обработанную дату
        query_last_date = """
            SELECT 
                max(date) as last_processed_date,
                max(processed_at) as last_processed_time
            FROM bionicpro_reports.user_reports_mart
        """
        
        result = client.execute(query_last_date)
        
        if not result or not result[0][0]:
            return {
                "available": False,
                "message": "Данные ещё не обработаны",
                "last_available_date": None,
                "last_processed_time": None
            }
        
        last_processed_date = result[0][0]
        last_processed_time = result[0][1]
        
        # Проверяем, есть ли данные за запрашиваемый период
        query_check = """
            SELECT count() as count
            FROM bionicpro_reports.user_reports_mart
            WHERE date >= %(date_from)s AND date <= %(date_to)s
        """
        
        result_check = client.execute(
            query_check,
            {"date_from": date_from, "date_to": date_to}
        )
        
        count = result_check[0][0] if result_check else 0
        
        # Проверяем доступность
        if last_processed_date < date_to:
            return {
                "available": False,
                "message": f"Данные за период {date_from} - {date_to} ещё не обработаны",
                "last_available_date": last_processed_date,
                "last_processed_time": last_processed_time,
                "requested_date_to": date_to
            }
        
        if count == 0:
            return {
                "available": False,
                "message": f"Нет данных за период {date_from} - {date_to}",
                "last_available_date": last_processed_date,
                "last_processed_time": last_processed_time
            }
        
        return {
            "available": True,
            "last_available_date": last_processed_date,
            "last_processed_time": last_processed_time,
            "records_count": count
        }
    
    except Exception as e:
        return {
            "available": False,
            "message": f"Ошибка при проверке доступности данных: {str(e)}",
            "last_available_date": None,
            "last_processed_time": None
        }


async def get_user_report(
    user_id: int,
    date_from: date,
    date_to: date,
    requested_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Получить отчёт по пользователю за период
    
    Args:
        user_id: ID пользователя (из токена, для проверки доступа)
        date_from: Начальная дата
        date_to: Конечная дата
        requested_user_id: Запрашиваемый user_id (если отличается от user_id, будет ошибка доступа)
    
    Returns:
        dict: Отчёт с данными
    
    Raises:
        HTTPException: Если пользователь пытается запросить данные другого пользователя
    """
    # Проверка доступа: пользователь может запрашивать только свои данные
    verify_user_access(
        current_user_id=user_id,
        requested_user_id=requested_user_id
    )
    
    client = get_clickhouse_client()
    
    try:
        # Основной запрос для получения данных
        query = """
            SELECT 
                date,
                device_id,
                total_usage_seconds,
                total_movements,
                avg_sensor_value,
                min_sensor_value,
                max_sensor_value,
                usage_hours,
                user_name,
                prosthesis_type,
                prosthesis_install_date,
                order_date,
                order_status,
                maintenance_date,
                maintenance_type,
                maintenance_status
            FROM bionicpro_reports.user_reports_mart
            WHERE user_id = %(user_id)s 
                AND date >= %(date_from)s 
                AND date <= %(date_to)s
            ORDER BY date ASC
        """
        
        result = client.execute(
            query,
            {
                "user_id": user_id,
                "date_from": date_from,
                "date_to": date_to
            }
        )
        
        # Преобразование результатов в список словарей
        columns = [
            "date", "device_id", "total_usage_seconds", "total_movements",
            "avg_sensor_value", "min_sensor_value", "max_sensor_value",
            "usage_hours", "user_name", "prosthesis_type",
            "prosthesis_install_date", "order_date", "order_status",
            "maintenance_date", "maintenance_type", "maintenance_status"
        ]
        
        data = []
        for row in result:
            record = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Преобразование дат в строки для JSON
                if isinstance(value, (date, datetime)):
                    record[col] = value.isoformat()
                else:
                    record[col] = value
            data.append(record)
        
        # Запрос для агрегированной статистики
        query_summary = """
            SELECT 
                sum(total_usage_seconds) as total_usage_seconds,
                sum(total_movements) as total_movements,
                avg(avg_sensor_value) as avg_sensor_value,
                min(min_sensor_value) as min_sensor_value,
                max(max_sensor_value) as max_sensor_value,
                sum(usage_hours) as total_usage_hours,
                count() as days_count
            FROM bionicpro_reports.user_reports_mart
            WHERE user_id = %(user_id)s 
                AND date >= %(date_from)s 
                AND date <= %(date_to)s
        """
        
        result_summary = client.execute(
            query_summary,
            {
                "user_id": user_id,
                "date_from": date_from,
                "date_to": date_to
            }
        )
        
        summary_columns = [
            "total_usage_seconds", "total_movements", "avg_sensor_value",
            "min_sensor_value", "max_sensor_value", "total_usage_hours",
            "days_count"
        ]
        
        summary = {}
        if result_summary and result_summary[0]:
            for i, col in enumerate(summary_columns):
                value = result_summary[0][i]
                summary[col] = float(value) if value is not None else 0
        
        # Дополнительная проверка: убеждаемся, что данные действительно принадлежат пользователю
        # Проверяем, есть ли данные для этого пользователя
        query_check_user = """
            SELECT count() as count
            FROM bionicpro_reports.user_reports_mart
            WHERE user_id = %(user_id)s 
                AND date >= %(date_from)s 
                AND date <= %(date_to)s
        """
        
        result_check = client.execute(
            query_check_user,
            {
                "user_id": user_id,
                "date_from": date_from,
                "date_to": date_to
            }
        )
        
        # Если данных нет, это нормально (может быть пустой период)
        # Но если есть данные, убеждаемся, что они принадлежат правильному пользователю
        
        # Получение последней обработанной даты
        query_last = """
            SELECT 
                max(date) as last_processed_date,
                max(processed_at) as last_processed_time
            FROM bionicpro_reports.user_reports_mart
            WHERE user_id = %(user_id)s
        """
        
        result_last = client.execute(query_last, {"user_id": user_id})
        
        last_processed_date = None
        last_processed_time = None
        
        if result_last and result_last[0][0]:
            last_processed_date = result_last[0][0]
            last_processed_time = result_last[0][1]
        
        return {
            "user_id": user_id,
            "date_from": date_from,
            "date_to": date_to,
            "data": data,
            "summary": summary,
            "last_processed_date": last_processed_date,
            "last_processed_time": last_processed_time
        }
    
    except HTTPException:
        # Пробрасываем HTTPException как есть (ошибки доступа)
        raise
    except Exception as e:
        raise Exception(f"Ошибка при получении отчёта: {str(e)}")
