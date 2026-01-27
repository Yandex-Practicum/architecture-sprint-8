from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import os
import psycopg2
from clickhouse_driver import Client

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'reports_etl',
    default_args=default_args,
    description='ETL process for reports: CRM + Telemetry -> ClickHouse',
    schedule_interval='0 2 * * *',
    catchup=False,
)

def extract_crm_data(**context):
    crm_host = os.getenv('CRM_DB_HOST', 'crm_db')
    crm_port = int(os.getenv('CRM_DB_PORT', '5432'))
    crm_db = os.getenv('CRM_DB_NAME', 'crm_db')
    crm_user = os.getenv('CRM_DB_USER', 'crm_user')
    crm_password = os.getenv('CRM_DB_PASSWORD', 'crm_password')
    
    conn = psycopg2.connect(
        host=crm_host,
        port=crm_port,
        database=crm_db,
        user=crm_user,
        password=crm_password
    )
    
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            c.id as customer_id,
            c.username,
            c.name as customer_name,
            c.email as customer_email,
            o.id as order_id,
            o.prosthesis_id,
            o.order_date,
            o.prosthesis_type
        FROM customers c
        LEFT JOIN orders o ON c.id = o.customer_id
        ORDER BY o.order_date DESC
    """)
    
    crm_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    context['ti'].xcom_push(key='crm_data', value=crm_data)
    return crm_data

def extract_telemetry_data(**context):
    telemetry_host = os.getenv('TELEMETRY_DB_HOST', 'telemetry_db')
    telemetry_port = int(os.getenv('TELEMETRY_DB_PORT', '5432'))
    telemetry_db = os.getenv('TELEMETRY_DB_NAME', 'telemetry_db')
    telemetry_user = os.getenv('TELEMETRY_DB_USER', 'telemetry_user')
    telemetry_password = os.getenv('TELEMETRY_DB_PASSWORD', 'telemetry_password')
    
    conn = psycopg2.connect(
        host=telemetry_host,
        port=telemetry_port,
        database=telemetry_db,
        user=telemetry_user,
        password=telemetry_password
    )
    
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            user_id,
            prosthesis_id,
            DATE(timestamp) as date,
            COUNT(*) as total_movements,
            AVG(reaction_time) as avg_reaction_time,
            MIN(reaction_time) as min_reaction_time,
            MAX(reaction_time) as max_reaction_time
        FROM telemetry
        GROUP BY user_id, prosthesis_id, DATE(timestamp)
        ORDER BY date DESC
    """)
    
    telemetry_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    context['ti'].xcom_push(key='telemetry_data', value=telemetry_data)
    return telemetry_data

def transform_and_load(**context):
    crm_data = context['ti'].xcom_pull(key='crm_data', task_ids='extract_crm')
    telemetry_data = context['ti'].xcom_pull(key='telemetry_data', task_ids='extract_telemetry')
    
    clickhouse_host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    clickhouse_port = int(os.getenv('CLICKHOUSE_PORT', '9000'))
    clickhouse_db = os.getenv('CLICKHOUSE_DB', 'reports_db')
    clickhouse_user = os.getenv('CLICKHOUSE_USER', 'default')
    clickhouse_password = os.getenv('CLICKHOUSE_PASSWORD', 'default')
    
    client = Client(
        host=clickhouse_host,
        port=clickhouse_port,
        database=clickhouse_db,
        user=clickhouse_user,
        password=clickhouse_password
    )
    
    crm_dict = {}
    for row in crm_data:
        customer_id, username, customer_name, customer_email, order_id, prosthesis_id, order_date, prosthesis_type = row
        if prosthesis_id:
            key = (username, prosthesis_id)
            if key not in crm_dict or (order_date and order_date > crm_dict[key].get('order_date', datetime.min)):
                crm_dict[key] = {
                    'username': username,
                    'customer_name': customer_name or '',
                    'customer_email': customer_email or '',
                    'prosthesis_id': prosthesis_id,
                    'order_date': order_date,
                    'prosthesis_type': prosthesis_type or ''
                }
    
    data_to_insert = []
    max_date = None
    
    for row in telemetry_data:
        user_id, prosthesis_id, date, total_movements, avg_reaction_time, min_reaction_time, max_reaction_time = row
        
        username = None
        customer_name = ''
        customer_email = ''
        order_date = None
        prosthesis_type = ''
        
        for key, value in crm_dict.items():
            if value['prosthesis_id'] == prosthesis_id:
                username = value['username']
                customer_name = value['customer_name']
                customer_email = value['customer_email']
                order_date = value['order_date']
                prosthesis_type = value['prosthesis_type']
                break
        
        if not username:
            username = user_id
        
        data_to_insert.append({
            'user_id': str(user_id),
            'username': str(username),
            'prosthesis_id': str(prosthesis_id),
            'date': date,
            'total_movements': int(total_movements) if total_movements else 0,
            'avg_reaction_time': float(avg_reaction_time) if avg_reaction_time else 0.0,
            'min_reaction_time': float(min_reaction_time) if min_reaction_time else 0.0,
            'max_reaction_time': float(max_reaction_time) if max_reaction_time else 0.0,
            'customer_name': str(customer_name),
            'customer_email': str(customer_email),
            'order_date': order_date if order_date else date,
            'prosthesis_type': str(prosthesis_type)
        })
        
        if max_date is None or date > max_date:
            max_date = date
    
    if data_to_insert:
        client.execute(
            'INSERT INTO reports_db.user_reports_mart VALUES',
            [[
                row['user_id'],
                row['username'],
                row['prosthesis_id'],
                row['date'],
                row['total_movements'],
                row['avg_reaction_time'],
                row['min_reaction_time'],
                row['max_reaction_time'],
                row['customer_name'],
                row['customer_email'],
                row['order_date'],
                row['prosthesis_type']
            ] for row in data_to_insert]
        )
    
    if max_date:
        client.execute(
            "INSERT INTO reports_db.etl_watermark (last_processed_date, updated_at) VALUES",
            [[max_date, datetime.now()]]
        )
    
    client.disconnect()
    return len(data_to_insert)

extract_crm_task = PythonOperator(
    task_id='extract_crm',
    python_callable=extract_crm_data,
    dag=dag,
)

extract_telemetry_task = PythonOperator(
    task_id='extract_telemetry',
    python_callable=extract_telemetry_data,
    dag=dag,
)

transform_load_task = PythonOperator(
    task_id='transform_and_load',
    python_callable=transform_and_load,
    dag=dag,
)

[extract_crm_task, extract_telemetry_task] >> transform_load_task
