from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine
from clickhouse_driver import Client

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'bionicpro_reports_datamart_etl',
    default_args=default_args,
    description='ETL pipeline for BionicPRO reports (CRM + Telemetry to ClickHouse)',
    schedule_interval='0 2 * * *',
    catchup=False,
    tags=['bionicpro', 'etl', 'reports'],
)

def build_and_load_datamart():
    # Extract
    crm_engine = create_engine('postgresql://crm_user:password@crm_db:5432/crm')
    telemetry_engine = create_engine('postgresql://api_user:password@api_db:5432/telemetry')

    crm_df = pd.read_sql("SELECT user_id, username, email, full_name FROM crm_users", crm_engine)

    telemetry_df = pd.read_sql("SELECT user_id, status, battery_level, motor_cycles, timestamp FROM telemetry_data", telemetry_engine)

    telemetry_df = telemetry_df.sort_values('timestamp')

    # Transform
    telemetry_grouped = telemetry_df.groupby('user_id').agg(
        total_motor_cycles=('motor_cycles', 'max'),
        latest_battery_level=('battery_level', 'last'),
        latest_status=('status', 'last'),
        last_sync_date=('timestamp', 'max')
    ).reset_index()

    datamart_df = pd.merge(crm_df, telemetry_grouped, on='user_id', how='inner')

    datamart_df['report_generated_at'] = datetime.now()


    # Load
    client = Client(host='clickhouse', user='admin', password='admin', database='bionicpro')
    client.execute('''
                   CREATE TABLE IF NOT EXISTS user_reports_datamart (
                                                                        user_id Int32,
                                                                        username String,
                                                                        email String,
                                                                        full_name String,
                                                                        total_motor_cycles Int32,
                                                                        latest_battery_level Int32,
                                                                        latest_status String,
                                                                        last_sync_date DateTime,
                                                                        report_generated_at DateTime
                   ) ENGINE = ReplacingMergeTree(report_generated_at)
                       ORDER BY (username, user_id)
                   ''')

    data_to_insert = datamart_df.to_dict('records')

    client.execute('INSERT INTO user_reports_datamart VALUES', data_to_insert)
    client.execute('OPTIMIZE TABLE user_reports_datamart FINAL')


etl_task = PythonOperator(
    task_id='build_reports_datamart',
    python_callable=build_and_load_datamart,
    dag=dag,
)

etl_task