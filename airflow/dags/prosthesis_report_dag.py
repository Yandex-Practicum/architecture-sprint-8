from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
import requests
import os

default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'prosthesis_etl_report',
    default_args=default_args,
    description='ETL для витрины отчётов из CSV',
    schedule_interval='0 3 * * *',
    catchup=False,
    tags=['bionicpro', 'report'],
)

DATA_DIR = '/opt/airflow/data'
TELEMETRY_FILE = f'{DATA_DIR}/telemetry.csv'
CRM_FILE = f'{DATA_DIR}/crm_data.csv'

def extract_telemetry(**context):
    """Чтение телеметрии из CSV и агрегация."""
    df = pd.read_csv(TELEMETRY_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    agg_df = df.groupby(['user_uuid', 'prosthesis_id']).agg({
        'usage_sec': 'sum',
        'response_time_ms': 'mean',
        'battery_cycles': 'max',
        'timestamp': 'max',
        'firmware_version': 'last'
    }).reset_index()
    
    agg_df.columns = ['user_uuid', 'prosthesis_id', 'total_usage_seconds',
                      'avg_response_time_ms', 'battery_cycles', 'last_telemetry_time', 'firmware_version']
    agg_df['movements_count'] = df.groupby(['user_uuid', 'prosthesis_id']).size().values
    
    # Преобразуем Timestamp в строку для JSON-сериализации
    agg_df['last_telemetry_time'] = agg_df['last_telemetry_time'].astype(str)
    
    context['ti'].xcom_push(key='telemetry_df', value=agg_df.to_dict())
    print(f"✅ Агрегировано {len(agg_df)} записей телеметрии")
    return agg_df

def extract_crm_data(**context):
    """Чтение данных клиентов из CSV."""
    df = pd.read_csv(CRM_FILE)
    df = df[df['status'] == 'active']
    context['ti'].xcom_push(key='crm_df', value=df.to_dict())
    print(f"✅ Загружено {len(df)} активных клиентов из CRM")
    return df

def transform_and_merge(**context):
    """Объединение телеметрии и CRM."""
    ti = context['ti']
    telemetry_dict = ti.xcom_pull(key='telemetry_df', task_ids='extract_telemetry')
    crm_dict = ti.xcom_pull(key='crm_df', task_ids='extract_crm_data')
    
    telemetry_df = pd.DataFrame.from_dict(telemetry_dict)
    crm_df = pd.DataFrame.from_dict(crm_dict)
    
    merged_df = telemetry_df.merge(crm_df[['user_uuid', 'full_name', 'region']], on='user_uuid', how='left')
    merged_df['report_date'] = datetime.now().date()
    merged_df['full_name'] = merged_df['full_name'].fillna('Unknown')
    merged_df['region'] = merged_df['region'].fillna('RU')
    merged_df['created_at'] = datetime.now()
    merged_df = merged_df.rename(columns={'full_name': 'user_name'})
    
    # Преобразуем даты в строки
    merged_df['report_date'] = merged_df['report_date'].astype(str)
    merged_df['created_at'] = merged_df['created_at'].astype(str)
    
    context['ti'].xcom_push(key='merged_df', value=merged_df.to_dict())
    print(f"✅ Объединено {len(merged_df)} записей")
    return merged_df

def load_to_clickhouse(**context):
    """Загрузка в ClickHouse через HTTP."""
    ti = context['ti']
    merged_dict = ti.xcom_pull(key='merged_df', task_ids='transform_and_merge')
    merged_df = pd.DataFrame.from_dict(merged_dict)
    
    # Обрезаем микросекунды у DateTime до секунд
    merged_df['last_telemetry_time'] = merged_df['last_telemetry_time'].str[:19]
    merged_df['created_at'] = merged_df['created_at'].str[:19]
    
    success_count = 0
    for _, row in merged_df.iterrows():
        query = f"""
        INSERT INTO reports_db.prosthesis_report 
        (user_uuid, user_name, prosthesis_id, report_date, total_usage_seconds,
         avg_response_time_ms, movements_count, battery_cycles, last_telemetry_time,
         firmware_version, region, created_at)
        VALUES (
            '{row['user_uuid']}', '{row['user_name']}', '{row['prosthesis_id']}', 
            '{row['report_date']}', {row['total_usage_seconds']}, {row['avg_response_time_ms']}, 
            {row['movements_count']}, {row['battery_cycles']}, '{row['last_telemetry_time']}', 
            '{row['firmware_version']}', '{row['region']}', '{row['created_at']}'
        )
        """
        response = requests.post(
            'http://clickhouse:8123/',
            params={'query': query},
            auth=('airflow', 'airflow123')
        )
        if response.status_code == 200:
            success_count += 1
        else:
            print(f"❌ Ошибка вставки: {response.text}")
    
    print(f"✅ Успешно загружено {success_count} из {len(merged_df)} записей в ClickHouse")
    return True

task_extract_telemetry = PythonOperator(task_id='extract_telemetry', python_callable=extract_telemetry, provide_context=True, dag=dag)
task_extract_crm = PythonOperator(task_id='extract_crm_data', python_callable=extract_crm_data, provide_context=True, dag=dag)
task_transform = PythonOperator(task_id='transform_and_merge', python_callable=transform_and_merge, provide_context=True, dag=dag)
task_load = PythonOperator(task_id='load_to_clickhouse', python_callable=load_to_clickhouse, provide_context=True, dag=dag)

[task_extract_telemetry, task_extract_crm] >> task_transform >> task_load