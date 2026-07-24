from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.dummy import DummyOperator
import pandas as pd
import os

default_args = {
    'owner': 'bionicpro',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2026, 7, 22),
}

dag = DAG(
    'user_report',
    default_args=default_args,
    description='ETL для витрины отчётов BionicPRO',
    schedule_interval='0 2 * * *', 
    catchup=False,
    tags=['bionicpro', 'etl'],
)

def extract_crm(**context):
    df = pd.read_csv('/opt/airflow/data/crm_users.csv')
    data = df.to_dict('records')
    context['task_instance'].xcom_push(key='crm_data', value=data)

def extract_sensors(**context):
    df = pd.read_csv('/opt/airflow/data/sensor_data.csv')
    data = df.to_dict('records')
    context['task_instance'].xcom_push(key='sensor_data', value=data)

def transform_and_join(**context):
    ti = context['task_instance']
    crm = ti.xcom_pull(key='crm_data', task_ids='extract_crm')
    sensors = ti.xcom_pull(key='sensor_data', task_ids='extract_sensors')
    
    crm_df = pd.DataFrame(crm)
    sensors_df = pd.DataFrame(sensors)
    
    sensor_agg = sensors_df.groupby('user_id').agg({
        'steps': 'sum',
        'active_minutes': 'sum',
        'battery_level': 'mean',
        'error_code': 'count'
    }).reset_index()
    sensor_agg.columns = ['user_id', 'total_steps', 'total_active_minutes', 
                          'avg_battery', 'error_count']
    
    final_df = crm_df.merge(sensor_agg, on='user_id', how='left')
    final_df = final_df.fillna({'total_steps': 0, 'total_active_minutes': 0, 
                                'avg_battery': 100, 'error_count': 0})
    final_df['report_date'] = datetime.now().date()
    
    context['task_instance'].xcom_push(key='mart_data', value=final_df.to_dict('records'))

def load_mart(**context):
    ti = context['task_instance']
    mart_data = ti.xcom_pull(key='mart_data', task_ids='transform_and_join')
    
    df = pd.DataFrame(mart_data)
    output_path = '/opt/airflow/data/user_report_mart.csv'
    df.to_csv(output_path, index=False)

start = DummyOperator(task_id='start', dag=dag)
end = DummyOperator(task_id='end', dag=dag)

extract_crm_task = PythonOperator(
    task_id='extract_crm',
    python_callable=extract_crm,
    dag=dag,
)

extract_sensors_task = PythonOperator(
    task_id='extract_sensors',
    python_callable=extract_sensors,
    dag=dag,
)

transform_task = PythonOperator(
    task_id='transform_and_join',
    python_callable=transform_and_join,
    dag=dag,
)

load_task = PythonOperator(
    task_id='load_mart',
    python_callable=load_mart,
    dag=dag,
)

start >> [extract_crm_task, extract_sensors_task] >> transform_task >> load_task >> end