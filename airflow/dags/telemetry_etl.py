from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
import clickhouse_connect
import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'email': ['airflow@bionicpro.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=30),
}

def extract_telemetry_data(execution_date, **context):
    logger.info(f"Extracting telemetry data for {execution_date}")
    
    pg_hook = PostgresHook(postgres_conn_id='postgres_telemetry')
    
    start_date = execution_date.replace(tzinfo=None) if hasattr(execution_date, 'replace') else execution_date
    end_date = (execution_date + timedelta(days=1)).replace(tzinfo=None)
    
    query = """
        SELECT 
            id,
            user_id,
            device_id,
            timestamp,
            sensor_type,
            sensor_value::TEXT as sensor_value,
            processing_time_ms,
            action_executed,
            created_at
        FROM sensor_data
        WHERE timestamp >= %s AND timestamp < %s
        ORDER BY timestamp
    """
    
    connection = pg_hook.get_conn()
    df = pd.read_sql(query, connection, params=[start_date, end_date])
    connection.close()
    
    logger.info(f"Extracted {len(df)} records from PostgreSQL")
    
    temp_file = f'/tmp/telemetry_{execution_date.strftime("%Y%m%d")}.parquet'
    df.to_parquet(temp_file, index=False)
    
    context['task_instance'].xcom_push(key='telemetry_file', value=temp_file)
    context['task_instance'].xcom_push(key='records_count', value=len(df))
    
    return temp_file


def transform_telemetry_data(**context):
    logger.info("Transforming telemetry data")
    
    temp_file = context['task_instance'].xcom_pull(key='telemetry_file', task_ids='extract_telemetry')
    
    df = pd.read_parquet(temp_file)
    
    initial_count = len(df)
    df = df.drop_duplicates(subset=['user_id', 'device_id', 'timestamp', 'sensor_type'])
    duplicates_removed = initial_count - len(df)
    logger.info(f"Removed {duplicates_removed} duplicate records")
    
    df = df.dropna(subset=['user_id', 'device_id', 'timestamp'])
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['created_at'] = pd.to_datetime(df['created_at'])
    
    df['action_executed'] = df['action_executed'].fillna('')
    df['sensor_value'] = df['sensor_value'].fillna('{}')
    df['processing_time_ms'] = df['processing_time_ms'].fillna(0.0)
    
    logger.info(f"Transformation complete. Final record count: {len(df)}")
    
    transformed_file = temp_file.replace('.parquet', '_transformed.parquet')
    df.to_parquet(transformed_file, index=False)
    
    context['task_instance'].xcom_push(key='transformed_file', value=transformed_file)
    context['task_instance'].xcom_push(key='final_records_count', value=len(df))
    
    return transformed_file


def load_to_clickhouse(**context):
    logger.info("Loading data to ClickHouse")
    
    transformed_file = context['task_instance'].xcom_pull(key='transformed_file', task_ids='transform_telemetry')
    
    df = pd.read_parquet(transformed_file)
    
    if len(df) == 0:
        logger.warning("No data to load into ClickHouse")
        return
    
    clickhouse_host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    clickhouse_port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
    clickhouse_user = os.getenv('CLICKHOUSE_USER', 'default')
    clickhouse_password = os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse')
    clickhouse_database = os.getenv('CLICKHOUSE_DATABASE', 'bionicpro')
    
    client = clickhouse_connect.get_client(
        host=clickhouse_host,
        port=clickhouse_port,
        username=clickhouse_user,
        password=clickhouse_password,
        database=clickhouse_database
    )
    
    try:
        client.insert_df(
            table='telemetry_raw',
            df=df,
            settings={'async_insert': 1, 'wait_for_async_insert': 1}
        )
        
        logger.info(f"Successfully loaded {len(df)} records into ClickHouse")
        
        result = client.query("SELECT count() FROM telemetry_raw")
        total_records = result.result_rows[0][0]
        logger.info(f"Total records in telemetry_raw table: {total_records}")
        
    except Exception as e:
        logger.error(f"Error loading data to ClickHouse: {e}")
        raise
    finally:
        client.close()
    
    try:
        temp_file = context['task_instance'].xcom_pull(key='telemetry_file', task_ids='extract_telemetry')
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
        if os.path.exists(transformed_file):
            os.remove(transformed_file)
        logger.info("Cleaned up temporary files")
    except Exception as e:
        logger.warning(f"Error cleaning up temp files: {e}")


def verify_data_quality(**context):
    logger.info("Verifying data quality in ClickHouse")
    
    clickhouse_host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    clickhouse_port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
    clickhouse_user = os.getenv('CLICKHOUSE_USER', 'default')
    clickhouse_password = os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse')
    clickhouse_database = os.getenv('CLICKHOUSE_DATABASE', 'bionicpro')
    
    client = clickhouse_connect.get_client(
        host=clickhouse_host,
        port=clickhouse_port,
        username=clickhouse_user,
        password=clickhouse_password,
        database=clickhouse_database
    )
    
    try:
        duplicate_check = client.query("""
            SELECT count(*) as duplicates
            FROM (
                SELECT user_id, device_id, timestamp, sensor_type, count() as cnt
                FROM telemetry_raw
                GROUP BY user_id, device_id, timestamp, sensor_type
                HAVING cnt > 1
            )
        """)
        duplicates = duplicate_check.result_rows[0][0]
        
        if duplicates > 0:
            logger.warning(f"Found {duplicates} duplicate records in ClickHouse")
        else:
            logger.info("No duplicates found - data quality check passed")
        
        null_check = client.query("""
            SELECT count(*) as null_records
            FROM telemetry_raw
            WHERE user_id = 0 OR device_id = '' OR timestamp = toDateTime(0)
        """)
        null_records = null_check.result_rows[0][0]
        
        if null_records > 0:
            logger.warning(f"Found {null_records} records with NULL values")
        else:
            logger.info("No NULL values in critical fields - data quality check passed")
            
    except Exception as e:
        logger.error(f"Error during data quality check: {e}")
        raise
    finally:
        client.close()


with DAG(
    'telemetry_etl',
    default_args=default_args,
    description='ETL процесс для телеметрии протезов',
    schedule_interval='0 1 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['bionicpro', 'etl', 'telemetry'],
    max_active_runs=1,
) as dag:
    
    extract_task = PythonOperator(
        task_id='extract_telemetry',
        python_callable=extract_telemetry_data,
        provide_context=True,
    )
    
    transform_task = PythonOperator(
        task_id='transform_telemetry',
        python_callable=transform_telemetry_data,
        provide_context=True,
    )
    
    load_task = PythonOperator(
        task_id='load_to_clickhouse',
        python_callable=load_to_clickhouse,
        provide_context=True,
    )
    
    verify_task = PythonOperator(
        task_id='verify_data_quality',
        python_callable=verify_data_quality,
        provide_context=True,
    )
    
    extract_task >> transform_task >> load_task >> verify_task
