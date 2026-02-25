import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class OlapService:
    """Сервис для работы с ClickHouse (OLAP) базой данных."""

    def __init__(self, config):
        self.clickhouse_url = config.CLICKHOUSE_HTTP_URL

    def _execute_query(self, query: str) -> Optional[str]:
        """Выполнить запрос к ClickHouse через HTTP API."""
        try:
            resp = requests.post(
                self.clickhouse_url,
                data=query,
                timeout=10
            )
            if resp.status_code != 200:
                logger.error(f"ClickHouse query error: {resp.text}")
                return None
            return resp.text
        except requests.exceptions.RequestException as e:
            logger.error(f"ClickHouse connection error: {str(e)}")
            return None

    def get_datamart_last_updated(self) -> Optional[str]:
        """
        Получить время последнего обновления витрины.
        Позволяет определить, обработал ли Airflow данные.
        """
        query = """
            SELECT max(updated_at)
            FROM customer_telemetry_datamart
            FORMAT JSONEachRow
        """
        result = self._execute_query(query)
        if result and result.strip():
            try:
                import json
                row = json.loads(result.strip().split('\n')[0])
                return row.get('max(updated_at)', None)
            except (json.JSONDecodeError, IndexError):
                return None
        return None

    def check_datamart_exists(self) -> bool:
        """Проверить, существует ли витрина и содержит ли данные."""
        query = "SELECT count() as cnt FROM customer_telemetry_datamart FORMAT JSONEachRow"
        result = self._execute_query(query)
        if result and result.strip():
            try:
                import json
                row = json.loads(result.strip())
                return int(row.get('cnt', 0)) > 0
            except (json.JSONDecodeError, ValueError):
                return False
        return False

    def get_user_report_by_email(self, email: str) -> Optional[Dict]:
        """
        Получить отчёт по пользователю из витрины customer_telemetry_datamart.
        Поиск по email — связь между Keycloak-пользователем и CRM-клиентом.
        Возвращает только данные конкретного пользователя (ограничение доступа).
        """
        # Экранируем email для безопасности запроса
        safe_email = email.replace("'", "\\'")

        query = f"""
            SELECT
                customer_id,
                customer_name,
                email,
                age,
                gender,
                country,
                prosthesis_type,
                muscle_group,
                total_signals,
                avg_signal_frequency,
                avg_signal_duration,
                avg_signal_amplitude,
                min_signal_amplitude,
                max_signal_amplitude,
                total_signal_duration,
                first_signal_time,
                last_signal_time,
                updated_at
            FROM customer_telemetry_datamart
            WHERE email = '{safe_email}'
            ORDER BY prosthesis_type, muscle_group
            FORMAT JSONEachRow
        """

        result = self._execute_query(query)
        if not result or not result.strip():
            return None

        import json
        rows = []
        for line in result.strip().split('\n'):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        if not rows:
            return None

        # Формируем структурированный отчёт
        first_row = rows[0]
        report = {
            'customer_id': first_row['customer_id'],
            'customer_name': first_row['customer_name'],
            'email': first_row['email'],
            'age': first_row['age'],
            'gender': first_row['gender'],
            'country': first_row['country'],
            'telemetry_summary': [],
            'report_generated_at': datetime.utcnow().isoformat() + 'Z',
            'data_updated_at': first_row.get('updated_at', 'unknown')
        }

        for row in rows:
            report['telemetry_summary'].append({
                'prosthesis_type': row['prosthesis_type'],
                'muscle_group': row['muscle_group'],
                'total_signals': row['total_signals'],
                'avg_signal_frequency': row['avg_signal_frequency'],
                'avg_signal_duration': row['avg_signal_duration'],
                'avg_signal_amplitude': row['avg_signal_amplitude'],
                'min_signal_amplitude': row['min_signal_amplitude'],
                'max_signal_amplitude': row['max_signal_amplitude'],
                'total_signal_duration': row['total_signal_duration'],
                'first_signal_time': row['first_signal_time'],
                'last_signal_time': row['last_signal_time'],
            })

        return report

    def get_user_report_by_id(self, customer_id: int) -> Optional[Dict]:
        """
        Получить отчёт по customer_id из витрины.
        Альтернативный метод поиска.
        """
        query = f"""
            SELECT
                customer_id,
                customer_name,
                email,
                age,
                gender,
                country,
                prosthesis_type,
                muscle_group,
                total_signals,
                avg_signal_frequency,
                avg_signal_duration,
                avg_signal_amplitude,
                min_signal_amplitude,
                max_signal_amplitude,
                total_signal_duration,
                first_signal_time,
                last_signal_time,
                updated_at
            FROM customer_telemetry_datamart
            WHERE customer_id = {int(customer_id)}
            ORDER BY prosthesis_type, muscle_group
            FORMAT JSONEachRow
        """

        result = self._execute_query(query)
        if not result or not result.strip():
            return None

        import json
        rows = []
        for line in result.strip().split('\n'):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        if not rows:
            return None

        first_row = rows[0]
        report = {
            'customer_id': first_row['customer_id'],
            'customer_name': first_row['customer_name'],
            'email': first_row['email'],
            'age': first_row['age'],
            'gender': first_row['gender'],
            'country': first_row['country'],
            'telemetry_summary': [],
            'report_generated_at': datetime.utcnow().isoformat() + 'Z',
            'data_updated_at': first_row.get('updated_at', 'unknown')
        }

        for row in rows:
            report['telemetry_summary'].append({
                'prosthesis_type': row['prosthesis_type'],
                'muscle_group': row['muscle_group'],
                'total_signals': row['total_signals'],
                'avg_signal_frequency': row['avg_signal_frequency'],
                'avg_signal_duration': row['avg_signal_duration'],
                'avg_signal_amplitude': row['avg_signal_amplitude'],
                'min_signal_amplitude': row['min_signal_amplitude'],
                'max_signal_amplitude': row['max_signal_amplitude'],
                'total_signal_duration': row['total_signal_duration'],
                'first_signal_time': row['first_signal_time'],
                'last_signal_time': row['last_signal_time'],
            })

        return report
