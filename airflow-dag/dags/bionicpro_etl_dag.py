from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime
import pandas as pd
import logging
from clickhouse_driver import Client

logger = logging.getLogger(__name__)

def etl_to_clickhouse():
    logger.info('STARTING ETL')

    ch = Client(host='clickhouse', port=9000, user='default', database='reports_db')

    # Загружаем CRM - разделитель ';'
    df_crm = pd.read_csv('/opt/airflow/sample_files/customers.csv', sep=';')

    # Преобразуем даты
    df_crm['registration_date'] = pd.to_datetime(df_crm['registration_date']).dt.date
    df_crm['last_active_date'] = pd.to_datetime(df_crm['last_active_date']).dt.date
    logger.info(f'CRM: {len(df_crm)} records')
    logger.info(f'First user: {df_crm.iloc[0]["user_id"]}')

    # Загружаем телеметрию
    pg_hook = PostgresHook(postgres_conn_id='telemetry_postgres')
    df_telemetry = pg_hook.get_pandas_df('''
                                         SELECT
                                             user_id,
                                             COUNT(*) as total_movements,
                                             AVG(reaction_time_ms) as avg_reaction_time,
                                             AVG(signal_quality) as avg_signal_quality,
                                             MIN(reaction_time_ms) as min_reaction_time,
                                             MAX(reaction_time_ms) as max_reaction_time,
                                             AVG(battery_level) as avg_battery_level
                                         FROM prosthesis_telemetry
                                         WHERE is_noise = false
                                         GROUP BY user_id
                                         ''')
    logger.info(f'Telemetry: {len(df_telemetry)} users')

    # Очищаем таблицу
    ch.execute('TRUNCATE TABLE user_report_mart')

    # Вставляем данные - используем безопасный метод с параметрами
    for _, row in df_crm.iterrows():
        user_id = row['user_id']
        tele_row = df_telemetry[df_telemetry['user_id'] == user_id]

        if not tele_row.empty:
            t = tele_row.iloc[0]
            total_movements = int(t['total_movements'])
            avg_reaction = float(t['avg_reaction_time'])
            avg_signal = float(t['avg_signal_quality'])
            min_reaction = int(t['min_reaction_time'])
            max_reaction = int(t['max_reaction_time'])
            avg_battery = int(t['avg_battery_level'])
            performance_score = round((100 - min(avg_reaction, 100)) * 0.5 + avg_signal * 30 + (avg_battery / 100) * 20, 2)
            needs_calibration = avg_signal < 0.8
        else:
            total_movements = 0
            avg_reaction = 0
            avg_signal = 0
            min_reaction = 0
            max_reaction = 0
            avg_battery = 0
            performance_score = 0
            needs_calibration = False

        # Экранируем кавычки в текстовых полях
        user_name = row['full_name'].replace("'", "''")
        email = row['email'].replace("'", "''")
        phone = row['phone'].replace("'", "''")
        prosthesis_model = row['prosthesis_model'].replace("'", "''")
        serial_number = row['serial_number'].replace("'", "''")

        ch.execute(f"""
            INSERT INTO user_report_mart (
                user_id, user_name, email, phone, prosthesis_model, serial_number, registration_date,
                total_movements, avg_reaction_time, median_reaction_time, min_reaction_time, max_reaction_time,
                avg_signal_quality, min_signal_quality, avg_battery_level,
                performance_score, needs_calibration, last_activity_date
            ) VALUES (
                '{user_id}', '{user_name}', '{email}', '{phone}', 
                '{prosthesis_model}', '{serial_number}', '{row['registration_date']}',
                {total_movements}, {avg_reaction}, {avg_reaction}, {min_reaction}, {max_reaction},
                {avg_signal}, {avg_signal}, {avg_battery},
                {performance_score}, {needs_calibration}, '{row['last_active_date']}'
            )
        """)

    count = ch.execute('SELECT COUNT(*) FROM user_report_mart')[0][0]
    logger.info(f'SUCCESS: Loaded {count} records')

    # Вывод топ пользователей
    top = ch.execute('SELECT user_name, total_movements, performance_score FROM user_report_mart ORDER BY performance_score DESC LIMIT 5')
    for row in top:
        logger.info(f'  {row[0]}: {row[1]} movements, {row[2]} score')

    return count

with DAG('bionicpro_etl', start_date=datetime(2026,5,1), schedule_interval='*/30 * * * *', catchup=False) as dag:
    task = PythonOperator(task_id='etl_to_clickhouse', python_callable=etl_to_clickhouse)