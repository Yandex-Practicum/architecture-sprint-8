from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import TaskInstance
from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator, SQLInsertRowsOperator
from airflow.sensors.time_delta import TimeDeltaSensor


def get_aggregated_data_from_xcom(ti: TaskInstance):
    return ti.xcom_pull(task_ids='aggregate_for_day')


def get_actual_persons_data_from_xcom(ti: TaskInstance):
    return ti.xcom_pull(task_ids='fetch_actual_persons')


default_args = {
    'owner': 'airflow',
    'start_date': datetime(2026, 7, 20),
}

# Определяем DAG
with (DAG('telemetry_to_dwh',
          default_args=default_args,
          schedule='@hourly', # Агрегирует данные телеметрии в отчет каждый час
          is_paused_upon_creation=False,
          catchup=False) as dag):
    delay_1_minute = TimeDeltaSensor(
        task_id='delay_1_minute',
        delta=timedelta(minutes=1),
        mode='reschedule',
        poke_interval=60,
        timeout=3600
    )

    delete_aggregated_for_day = SQLExecuteQueryOperator(
        task_id='delete_user_daily_measurements',
        conn_id='dwh_connection',
        split_statements=True,
        sql="TRUNCATE user_daily_measurements;"
            "TRUNCATE actual_persons"
    )

    aggregate_for_day = SQLExecuteQueryOperator(
        task_id='aggregate_for_day',
        conn_id='telemetry_connection',
        sql="SELECT username, device_id, type, avg(value) FROM measurements WHERE"
            " timestamp::date = '{{ ds }}'"
            " AND type in ('battery_level', 'tension', 'impedance')"
            " GROUP BY username, device_id, type",
        return_last=True,
        do_xcom_push=True,
        autocommit=True
    )

    buffer_aggregated_data = PythonOperator(
        task_id='buffer_aggregated_data',
        python_callable=get_aggregated_data_from_xcom,
        provide_context=True
    )

    insert_aggregated = SQLInsertRowsOperator(
        task_id='insert_aggregated',
        conn_id='dwh_connection',
        table_name="user_daily_measurements",
        columns=["username", "device_id", "type", "avg_value"],
        rows=buffer_aggregated_data.output
    )

    fetch_actual_persons = SQLExecuteQueryOperator(
        task_id='fetch_actual_persons',
        conn_id='crm_connection',
        sql="SELECT"
            " username, first_name, last_name, gender,  EXTRACT(YEAR FROM AGE('{{ ds }}'::date, dob)), profession,"
            " d.id, d.name"
            " FROM persons p"
            " LEFT JOIN person_devices pd ON pd.owner = p.username"
            " LEFT JOIN devices d ON d.id = pd.device_id",
        return_last=True,
        do_xcom_push=True,
        autocommit=True
    )

    buffer_actual_persons_data = PythonOperator(
        task_id='buffer_actual_persons_data',
        python_callable=get_actual_persons_data_from_xcom,
        provide_context=True
    )

    insert_actual_persons = SQLInsertRowsOperator(
        task_id='insert_actual_persons',
        conn_id='dwh_connection',
        table_name="actual_persons",
        columns=["username", "first_name", "last_name", "gender", "age", "profession", "device_id", "device_name"],
        rows=buffer_actual_persons_data.output
    )

    aggregate_daily_report = SQLExecuteQueryOperator(
        task_id='aggregate_daily_report',
        conn_id='dwh_connection',
        sql="""
            INSERT INTO user_daily_report
             (username, day, first_name, last_name, gender, age, profession,
              device_id, device_name, avg_battery_level, avg_tension, avg_impedance) 
            SELECT p.username, '{{ ds }}', p.first_name, p.last_name, p.gender, p.age, p.profession, 
                p.device_id, p.device_name,
                (SELECT avg_value FROM user_daily_measurements WHERE username = p.username AND device_id = p.device_id AND type = 'battery_level'),
                (SELECT avg_value FROM user_daily_measurements WHERE username = p.username AND device_id = p.device_id AND type = 'tension'),
                (SELECT avg_value FROM user_daily_measurements WHERE username = p.username AND device_id = p.device_id AND type = 'impedance')
            FROM actual_persons p
            ON CONFLICT (username, day, device_id) DO UPDATE 
              SET
                avg_battery_level = excluded.avg_battery_level,
                avg_tension = excluded.avg_tension,
                avg_impedance = excluded.avg_impedance;
        """
    )

    delay_1_minute >> delete_aggregated_for_day >> aggregate_for_day >> buffer_aggregated_data >> insert_aggregated
    delay_1_minute >> delete_aggregated_for_day >> fetch_actual_persons >> buffer_actual_persons_data >> insert_actual_persons
    insert_aggregated >> aggregate_daily_report
    insert_actual_persons >> aggregate_daily_report
