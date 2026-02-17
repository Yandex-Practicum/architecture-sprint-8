from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
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
    'execution_timeout': timedelta(minutes=20),
}

def extract_crm_data(execution_date, **context):
    logger.info(f"Extracting CRM data for {execution_date}")
    
    pg_hook = PostgresHook(postgres_conn_id='postgres_crm')
    
    query = """
        SELECT 
            c.id as user_id,
            c.email,
            c.full_name,
            c.phone,
            c.country,
            c.registration_date,
            c.is_active::INT as is_active,
            
            -- Данные о протезе
            pd.device_id,
            pd.device_type,
            pd.serial_number,
            pd.manufacture_date,
            pd.delivery_date,
            pd.warranty_until,
            pd.status as device_status,
            
            -- Данные профиля
            up.date_of_birth,
            up.amputation_type,
            up.amputation_date
            
        FROM customers c
        LEFT JOIN prosthetic_devices pd ON c.id = pd.user_id
        LEFT JOIN user_profiles up ON c.id = up.user_id
        WHERE c.is_active = TRUE
        ORDER BY c.id
    """
    
    connection = pg_hook.get_conn()
    df = pd.read_sql(query, connection)
    connection.close()
    
    logger.info(f"Extracted {len(df)} records from CRM PostgreSQL")
    
    temp_file = f'/tmp/crm_{execution_date.strftime("%Y%m%d")}.parquet'
    df.to_parquet(temp_file, index=False)
    
    context['task_instance'].xcom_push(key='crm_file', value=temp_file)
    context['task_instance'].xcom_push(key='records_count', value=len(df))
    
    return temp_file


def transform_crm_data(**context):
    logger.info("Transforming CRM data")
    
    temp_file = context['task_instance'].xcom_pull(key='crm_file', task_ids='extract_crm')
    
    df = pd.read_parquet(temp_file)
    
    initial_count = len(df)
    df = df.drop_duplicates(subset=['user_id', 'device_id'])
    duplicates_removed = initial_count - len(df)
    logger.info(f"Removed {duplicates_removed} duplicate records")
    
    df = df.dropna(subset=['user_id', 'email'])
    
    df['registration_date'] = pd.to_datetime(df['registration_date'])
    df['manufacture_date'] = pd.to_datetime(df['manufacture_date'])
    df['delivery_date'] = pd.to_datetime(df['delivery_date'])
    df['warranty_until'] = pd.to_datetime(df['warranty_until'])
    df['date_of_birth'] = pd.to_datetime(df['date_of_birth'])
    df['amputation_date'] = pd.to_datetime(df['amputation_date'])
    
    df['phone'] = df['phone'].fillna('')
    df['device_id'] = df['device_id'].fillna('')
    df['device_type'] = df['device_type'].fillna('')
    df['serial_number'] = df['serial_number'].fillna('')
    df['device_status'] = df['device_status'].fillna('unknown')
    df['amputation_type'] = df['amputation_type'].fillna('')
    
    df['is_active'] = df['is_active'].astype(int)
    
    logger.info(f"Transformation complete. Final record count: {len(df)}")
    
    transformed_file = temp_file.replace('.parquet', '_transformed.parquet')
    df.to_parquet(transformed_file, index=False)
    
    context['task_instance'].xcom_push(key='transformed_file', value=transformed_file)
    context['task_instance'].xcom_push(key='final_records_count', value=len(df))
    
    return transformed_file


def load_to_clickhouse(**context):
    logger.info("Loading CRM data to ClickHouse")
    
    transformed_file = context['task_instance'].xcom_pull(key='transformed_file', task_ids='transform_crm')
    
    df = pd.read_parquet(transformed_file)
    
    if len(df) == 0:
        logger.warning("No CRM data to load into ClickHouse")
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
        client.command("TRUNCATE TABLE crm_data")
        logger.info("Truncated crm_data table")
        
        client.insert_df(
            table='crm_data',
            df=df,
            settings={'async_insert': 1, 'wait_for_async_insert': 1}
        )
        
        logger.info(f"Successfully loaded {len(df)} CRM records into ClickHouse")
        
        result = client.query("SELECT count() FROM crm_data")
        total_records = result.result_rows[0][0]
        logger.info(f"Total records in crm_data table: {total_records}")
        
    except Exception as e:
        logger.error(f"Error loading CRM data to ClickHouse: {e}")
        raise
    finally:
        client.close()
    
    try:
        temp_file = context['task_instance'].xcom_pull(key='crm_file', task_ids='extract_crm')
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
        if os.path.exists(transformed_file):
            os.remove(transformed_file)
        logger.info("Cleaned up temporary files")
    except Exception as e:
        logger.warning(f"Error cleaning up temp files: {e}")


def verify_crm_data_quality(**context):
    logger.info("Verifying CRM data quality in ClickHouse")
    
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
        user_count = client.query("SELECT countDistinct(user_id) FROM crm_data")
        unique_users = user_count.result_rows[0][0]
        logger.info(f"Unique users in CRM data: {unique_users}")
        
        devices_count = client.query("""
            SELECT count(*) 
            FROM crm_data 
            WHERE device_id != ''
        """)
        users_with_devices = devices_count.result_rows[0][0]
        logger.info(f"Users with devices: {users_with_devices}")
        
        empty_email = client.query("""
            SELECT count(*) 
            FROM crm_data 
            WHERE email = ''
        """)
        empty_emails_count = empty_email.result_rows[0][0]
        
        if empty_emails_count > 0:
            logger.warning(f"Found {empty_emails_count} records with empty email")
        else:
            logger.info("All records have valid email - data quality check passed")
            
    except Exception as e:
        logger.error(f"Error during CRM data quality check: {e}")
        raise
    finally:
        client.close()


with DAG(
    'crm_etl',
    default_args=default_args,
    description='ETL процесс для CRM данных (клиенты и протезы)',
    schedule_interval='0 2 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['bionicpro', 'etl', 'crm'],
    max_active_runs=1,
) as dag:
    
    extract_task = PythonOperator(
        task_id='extract_crm',
        python_callable=extract_crm_data,
        provide_context=True,
    )
    
    transform_task = PythonOperator(
        task_id='transform_crm',
        python_callable=transform_crm_data,
        provide_context=True,
    )
    
    load_task = PythonOperator(
        task_id='load_to_clickhouse',
        python_callable=load_to_clickhouse,
        provide_context=True,
    )
    
    verify_task = PythonOperator(
        task_id='verify_crm_data_quality',
        python_callable=verify_crm_data_quality,
        provide_context=True,
    )
    
    extract_task >> transform_task >> load_task >> verify_task
