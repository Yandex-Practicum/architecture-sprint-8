from datetime import datetime, timedelta
import pandas as pd
import json
from collections import Counter
from io import StringIO
import logging
import csv
from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow_clickhouse_plugin.hooks.clickhouse import ClickHouseHook
from airflow.operators.python_operator import PythonOperator
from helper import xcom_to_df, df_to_xcom, parse_datetime

default_config = {
    'owner': 'data_engineer',
    'depends_on_past': False,
    'start_date': datetime(2025, 4, 5),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

etl_dag = DAG(
    'crm_to_clickhouse_mart_dag',
    default_args=default_config,
    description='ETL: CRM + Telemetry → ClickHouse Mart',
    schedule_interval='0 2 * * *',
    catchup=False,
    tags=['etl', 'clickhouse', 'crm'],
)


def get_postgres_customers(**kwargs):
    logging.info("Получение данных клиентов из PostgreSQL")
    pg_connection = PostgresHook(postgres_conn_id='crm_db_conn')
    customer_data = pg_connection.get_pandas_df("""
                                                SELECT id AS user_id,
                                                       name,
                                                       email,
                                                       age,
                                                       gender,
                                                       country,
                                                       address,
                                                       phone
                                                FROM customers;
                                                """)

    if customer_data.empty:
        raise ValueError("Отсутствуют данные в таблице customers.")

    csv_content = StringIO()
    customer_data.to_csv(csv_content, index=False)
    serialized_data = csv_content.getvalue()

    kwargs['ti'].xcom_push(key='users_data', value=serialized_data)
    logging.info(f"Получено записей: {len(customer_data)}")


extract_customers = PythonOperator(
    task_id='extract_users_from_postgres',
    python_callable=get_postgres_customers,
    dag=etl_dag,
)


def process_telemetry_data(**kwargs):
    logging.info("Загрузка и обработка телеметрии")
    ch_connection = ClickHouseHook(clickhouse_conn_id='clickhouse_conn')

    column_names = ['user_id', 'prosthesis_type', 'muscle_group', 'signal_frequency',
                    'signal_duration', 'signal_amplitude', 'signal_time']

    query_string = f"""
        SELECT {", ".join(column_names)}
        FROM emg_sensor_data
    """

    try:
        result_set = ch_connection.execute(query_string)
    except Exception as exc:
        logging.error(f"Ошибка запроса: {exc}")
        raise

    if not result_set:
        logging.warning("Телеметрия отсутствует")
        telemetry_dataframe = pd.DataFrame(columns=column_names)
    else:
        telemetry_dataframe = pd.DataFrame(result_set, columns=column_names)
        telemetry_dataframe['user_id'] = pd.to_numeric(telemetry_dataframe['user_id'],
                                                       errors='coerce').fillna(0).astype('int')
        telemetry_dataframe['signal_time'] = pd.to_datetime(telemetry_dataframe['signal_time'],
                                                            errors='coerce')

    logging.info(f"Загружено телеметрии: {len(telemetry_dataframe)}")

    if telemetry_dataframe.empty:
        aggregated_data = pd.DataFrame(columns=[
            'user_id', 'total_signals', 'avg_signal_duration_sec',
            'avg_signal_amplitude', 'max_frequency', 'last_signal_time', 'muscle_usage_count'
        ])
        logging.info("Нет данных для агрегации")
    else:
        aggregated_data = telemetry_dataframe.groupby('user_id').agg({
            'signal_time': ['count', 'max'],
            'signal_duration': 'mean',
            'signal_amplitude': 'mean',
            'signal_frequency': 'max',
            'muscle_group': lambda vals: json.dumps(dict(Counter(vals.tolist())),
                                                    ensure_ascii=False)
        }).reset_index()

        aggregated_data.columns = [
            'user_id',
            'total_signals',
            'last_signal_time',
            'avg_signal_duration_sec',
            'avg_signal_amplitude',
            'max_frequency',
            'muscle_usage_count'
        ]

    column_defaults = {
        'total_signals': 0,
        'avg_signal_duration_sec': 0.0,
        'avg_signal_amplitude': 0.0,
        'max_frequency': 0.0,
        'last_signal_time': None,
        'muscle_usage_count': '{"unknown": 0}'
    }

    for column_name, default_value in column_defaults.items():
        if column_name not in aggregated_data.columns:
            aggregated_data[column_name] = default_value
        elif aggregated_data[column_name].isnull().any():
            if isinstance(default_value, str):
                aggregated_data[column_name] = aggregated_data[column_name].fillna(str(default_value))
            else:
                aggregated_data[column_name] = aggregated_data[column_name].fillna(default_value)

    if 'last_signal_time' in aggregated_data.columns:
        aggregated_data['last_signal_time'] = aggregated_data['last_signal_time'].where(
            pd.notna(aggregated_data['last_signal_time']), None
        )

    df_to_xcom(aggregated_data, kwargs['ti'], 'aggregated_telemetry')
    logging.info(f"Агрегировано записей: {len(aggregated_data)}")


process_telemetry = PythonOperator(
    task_id='extract_telemetry_from_clickhouse',
    python_callable=process_telemetry_data,
    dag=etl_dag,
)


def combine_datasets(**kwargs):
    logging.info("Объединение данных клиентов и телеметрии")
    task_instance = kwargs['ti']

    customer_dataframe = xcom_to_df(task_instance, 'extract_users_from_postgres', 'users_data')
    telemetry_dataframe = xcom_to_df(task_instance, 'extract_telemetry_from_clickhouse',
                                     'aggregated_telemetry')

    combined_dataframe = pd.merge(customer_dataframe, telemetry_dataframe,
                                  on='user_id', how='left')

    fill_config = {
        'total_signals': 0,
        'avg_signal_duration_sec': 0.0,
        'avg_signal_amplitude': 0.0,
        'max_frequency': 0,
        'muscle_usage_count': '{"unknown": 0}',
        'last_signal_time': pd.NaT
    }
    combined_dataframe.fillna(value=fill_config, inplace=True)

    combined_dataframe['user_id'] = combined_dataframe['user_id'].astype('int32')
    combined_dataframe['total_signals'] = combined_dataframe['total_signals'].astype('int32')
    combined_dataframe['avg_signal_duration_sec'] = combined_dataframe['avg_signal_duration_sec'].astype('float32')
    combined_dataframe['avg_signal_amplitude'] = combined_dataframe['avg_signal_amplitude'].astype('float32')
    combined_dataframe['max_frequency'] = combined_dataframe['max_frequency'].astype('int32')

    df_to_xcom(combined_dataframe, task_instance, 'mart_data')
    logging.info(f"Сформирована витрина: {len(combined_dataframe)} строк")


merge_data = PythonOperator(
    task_id='join_crm_with_telemetry',
    python_callable=combine_datasets,
    dag=etl_dag,
)


def initialize_mart_table(**kwargs):
    logging.info("Инициализация таблицы витрины")
    ch_connection = ClickHouseHook(clickhouse_conn_id='clickhouse_conn')

    logging.info("Очистка предыдущей таблицы")
    ch_connection.execute("DROP TABLE IF EXISTS report_patient_activity_mart")

    table_definition = """
                       CREATE TABLE IF NOT EXISTS report_patient_activity_mart \
                       ( \
                           user_id                 Int32, \
                           name                    String, \
                           age                     Int32, \
                           gender                  String, \
                           email                   String, \
                           country                 String, \
                           total_signals           Int32, \
                           avg_signal_duration_sec Float32, \
                           avg_signal_amplitude    Float32, \
                           max_frequency           Int32, \
                           last_signal_time        DateTime, \
                           muscle_usage_count      String
                       ) ENGINE = MergeTree()
    ORDER BY (user_id) \
                       """

    ch_connection.execute(table_definition)
    logging.info("Таблица витрины готова")


setup_table = PythonOperator(
    task_id='create_mart_table',
    python_callable=initialize_mart_table,
    dag=etl_dag,
)


def import_to_clickhouse(**kwargs):
    logging.info("Импорт данных в ClickHouse")
    task_instance = kwargs['ti']
    data_content = task_instance.xcom_pull(task_ids='join_crm_with_telemetry',
                                           key='mart_data')

    if not data_content:
        raise ValueError("Отсутствуют данные для импорта")

    data_reader = csv.DictReader(StringIO(data_content))
    records = []

    for data_row in data_reader:
        prepared_record = (
            int(data_row['user_id']),
            data_row['name'],
            int(float(data_row['age'])) if data_row['age'] else 0,
            data_row['gender'],
            data_row['email'],
            data_row['country'],
            int(data_row['total_signals']),
            float(data_row['avg_signal_duration_sec']),
            float(data_row['avg_signal_amplitude']),
            int(data_row['max_frequency']),
            parse_datetime(data_row['last_signal_time']),
            data_row['muscle_usage_count']
        )
        records.append(prepared_record)

    if not records:
        logging.info("Нет записей для импорта")
        return

    ch_connection = ClickHouseHook(clickhouse_conn_id='clickhouse_conn')
    ch_connection.execute("INSERT INTO report_patient_activity_mart VALUES", records)
    logging.info(f"Импортировано записей: {len(records)}")


import_data = PythonOperator(
    task_id='load_mart_to_clickhouse',
    python_callable=import_to_clickhouse,
    dag=etl_dag,
)

extract_customers >> merge_data
process_telemetry >> merge_data

merge_data >> setup_table >> import_data