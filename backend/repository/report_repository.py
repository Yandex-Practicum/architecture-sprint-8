from clickhouse_driver import Client
from config import CLICKHOUSE_HOST, CLICKHOUSE_DB

class ReportRepository:

    def __init__(self):
        self.client = Client(host=CLICKHOUSE_HOST, database=CLICKHOUSE_DB)
        self.client.execute("""
        CREATE TABLE IF NOT EXISTS default.report_user_prosthesis_daily (
            user_id UInt64,
            report_date Date,
            some_metric Float64
        ) ENGINE = MergeTree()
        ORDER BY (user_id, report_date)
        """)

    def get_max_report_date(self):
        return self.client.execute(
            "SELECT max(report_date) FROM report_user_prosthesis_daily"
        )[0][0]

    def load_report(self, user_id: str, from_date, to_date):
        query = f"""
        SELECT report_date, prosthesis_id, active_seconds, avg_reaction_ms,
               movements, errors, battery_avg, crm_country, crm_segment, crm_tariff
        FROM report_user_daily
        WHERE user_id = '{user_id}'
          AND report_date BETWEEN '{from_date}' AND '{to_date}'
        """
        rows = self.client.execute(query)
        return rows