from clickhouse_driver import Client
from config import CLICKHOUSE_HOST, CLICKHOUSE_PORT

client = Client(
    host=CLICKHOUSE_HOST,
    port=CLICKHOUSE_PORT,
    database='prosthetic_reports',
    settings={'use_numpy': False},
)

def get_report(user_id: int, date_from: str = None, date_to: str = None) -> list:
    query = """
        SELECT
            user_id, full_name, email, country, date,
            total_readings,
            avg_signal_1,
            avg_signal_2,
            avg_signal_3,
            avg_signal_4,
            avg_battery_level,
            movement_grasp,
            movement_release,
            movement_flex,
            movement_extend,
            movement_rotate
        FROM report_mart
        WHERE user_id = %(user_id)s
    """
    params = {'user_id': user_id}

    if date_from:
        query += " AND date >= %(date_from)s"
        params['date_from'] = date_from
    if date_to:
        query += " AND date <= %(date_to)s"
        params['date_to'] = date_to

    query += " ORDER BY date"

    return client.execute(query, params)
