from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow_clickhouse_plugin.hooks.clickhouse import ClickHouseHook
from datetime import datetime
from datetime import timedelta
import pandas as pd
import logging

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def extract_crm_data():
    pg_hook = PostgresHook(postgres_conn_id='crm_db')
    connection = pg_hook.get_conn()
    cursor = connection.cursor()
    cursor.execute("SELECT id, full_name, email, country, age FROM crm_customers;")
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=['id', 'full_name', 'email', 'country', 'age'])

    logging.info("CRM data extracted and saved to /tmp/crm_data.csv")
    logging.info(f"Extracted {len(df)} records from CRM database.")

    return df.to_dict(orient='records')

def extract_telemetry_data():
    pg_hook = PostgresHook(postgres_conn_id='telemetry_db')
    connection = pg_hook.get_conn()
    cursor = connection.cursor()
    cursor.execute("SELECT id, event_time, user_id, prosthesis_id, movement, battery_level, active_minutes FROM telemetry_data;")
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=['id', 'event_time', 'user_id', 'prosthesis_id', 'movement', 'battery_level', 'active_minutes'])
    df['event_time'] = pd.to_datetime(df['event_time']).dt.strftime('%Y-%m-%d %H:%M:%S')

    logging.info("Telemetry data extracted and saved to /tmp/telemetry_data.csv")
    logging.info(f"Extracted {len(df)} records from Telemetry database.")

    return df.to_dict(orient='records')

def join_data(**kwargs):
    ti = kwargs['ti']
    crm_data = ti.xcom_pull(task_ids='extract_crm_data')
    telemetry_data = ti.xcom_pull(task_ids='extract_telemetry_data')
    crm_df = pd.DataFrame(crm_data).rename(columns={'id': 'user_id'})
    telemetry_df = pd.DataFrame(telemetry_data)
    merged_df = pd.merge(telemetry_df, crm_df, on='user_id', how='left')

    logging.info("Data joined and saved to /tmp/merged_data.csv")
    logging.info(f"Joined {len(merged_df)} records.")
    return merged_df.to_dict(orient='records')

def load_to_clickhouse(**kwargs):
    dag_run_start_date = kwargs['dag_run'].start_date
    ti = kwargs['ti']
    merged_data = ti.xcom_pull(task_ids='join_data')
    if not merged_data:
        logging.warning("No data to load into ClickHouse.")
        return
    
    df_merge = pd.DataFrame(merged_data)

    if 'id' in df_merge.columns:
        df_merge = df_merge.drop(columns=['id'])


    df_merge['event_time'] = pd.to_datetime(df_merge['event_time'])
    df_merge['report_date'] = pd.to_datetime(dag_run_start_date)

    clickhouse_hook = ClickHouseHook(clickhouse_conn_id='clickhouse')

    columns = ', '.join(df_merge.columns)

    insert_query = f"INSERT INTO report ({columns}) VALUES"
    update_date_query = "INSERT INTO report_date (id, report_date) VALUES"

    try:
        clickhouse_hook.execute(insert_query, df_merge.values.tolist())
        clickhouse_hook.execute(update_date_query, [[1, dag_run_start_date]])
        logging.info("Data loaded into ClickHouse successfully.")
    except Exception as e:
        logging.error(f"Error loading data into ClickHouse: {e}")
        raise

def delete_old_data(**kwargs):
    dag_run_start_date = kwargs['dag_run'].start_date.strftime('%Y-%m-%d %H:%M:%S')
    clickhouse_hook = ClickHouseHook(clickhouse_conn_id='clickhouse')

    delete_query = f"DELETE FROM report WHERE report_date < '{dag_run_start_date}' "

    try:
        clickhouse_hook.execute(delete_query)
        logging.info("Old data deleted from ClickHouse successfully.")
    except Exception as e:
        logging.error(f"Error deleting old data from ClickHouse: {e}")
        raise

with DAG('dag_olap', default_args=default_args, schedule_interval='@daily', catchup=False) as dag:
    extract_crm = PythonOperator(
        task_id='extract_crm_data',
        python_callable=extract_crm_data
    )

    extract_telemetry = PythonOperator(
        task_id='extract_telemetry_data',
        python_callable=extract_telemetry_data
    )

    join = PythonOperator(
        task_id='join_data',
        python_callable=join_data,
        provide_context=True
    )

    load = PythonOperator(
        task_id='load_to_clickhouse',
        python_callable=load_to_clickhouse,
        provide_context=True
    )

    delete_old = PythonOperator(
        task_id='delete_old_data',
        python_callable=delete_old_data,
        provide_context=True
    )

    [extract_crm, extract_telemetry] >> join >> load >> delete_old


