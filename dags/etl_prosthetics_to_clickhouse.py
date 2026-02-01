from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.hooks.postgres_hook import PostgresHook
from datetime import datetime, timedelta
import logging
from clickhouse_driver import Client as ClickHouseClient

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# --- Extract Functions ---

def extract_clients_data(**context):
    pg_hook = PostgresHook(postgres_conn_id='crm_db_conn')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    query = """
    SELECT 
        client_id,
        external_client_id,
        first_name,
        last_name,
        email,
        phone,
        date_of_birth,
        registration_date,
        CASE WHEN is_active THEN 1 ELSE 0 END
    FROM clients
    """

    cursor.execute(query)
    rows = cursor.fetchall()
    data = [
        [
            row[0], row[1], row[2], row[3], row[4],
            row[5] or '', row[6], row[7], row[8],
            datetime.now(), datetime.now(), None
        ]
        for row in rows
    ]

    cursor.close()
    conn.close()
    logging.info(f"✅ Extracted {len(data)} clients")
    context['ti'].xcom_push(key='clients_data', value=data)


def extract_devices_data(**context):
    pg_hook = PostgresHook(postgres_conn_id='crm_db_conn')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    query = """
    SELECT 
        device_id, client_id, device_name, device_type, serial_number,
        manufacturing_date, activation_date, warranty_until,
        CASE WHEN is_active THEN 1 ELSE 0 END, last_maintenance_date
    FROM devices
    """

    cursor.execute(query)
    rows = cursor.fetchall()
    data = [
        [
            row[0], row[1], row[2] or '', row[3], row[4],
            row[5], row[6], row[7], row[8], row[9],
            datetime.now(), datetime.now(), None
        ]
        for row in rows
    ]

    cursor.close()
    conn.close()
    logging.info(f"✅ Extracted {len(data)} devices")
    context['ti'].xcom_push(key='devices_data', value=data)


def extract_telemetry_data(**context):
    pg_hook = PostgresHook(postgres_conn_id='telemetry_db_conn')
    conn = pg_hook.get_conn()
    cursor = conn.cursor()

    last_24_hours = datetime.now() - timedelta(hours=24)
    query = """
    SELECT 
        telemetry_id, device_id, timestamp,
        battery_level::float, temperature::float, pressure_sensor_reading::float,
        flexion_angle::float, step_count, error_code,
        accelerometer_x::float, accelerometer_y::float, accelerometer_z::float
    FROM device_telemetry
    WHERE timestamp >= %s
    """

    cursor.execute(query, (last_24_hours,))
    rows = cursor.fetchall()
    data = [
        [
            row[0], row[1], row[2],
            float(row[3]) if row[3] else 0.0,
            float(row[4]) if row[4] else 0.0,
            float(row[5]) if row[5] else 0.0,
            float(row[6]) if row[6] else 0.0,
            row[7] or 0, row[8] or 0,
            float(row[9]) if row[9] else 0.0,
            float(row[10]) if row[10] else 0.0,
            float(row[11]) if row[11] else 0.0,
            datetime.now(),
            'device_telemetry'
        ]
        for row in rows
    ]

    cursor.close()
    conn.close()
    logging.info(f"✅ Extracted {len(data)} telemetry records")
    context['ti'].xcom_push(key='telemetry_data', value=data)


# --- Load Functions ---

def load_clients_to_clickhouse(**context):
    client = ClickHouseClient(host='clickhouse', port=9000, user='admin', password='admin123', database='prosthetics_mart')
    try:
        data = context['ti'].xcom_pull(task_ids='extract_clients_data', key='clients_data')
        if data:
            client.execute('TRUNCATE TABLE clients_dimension')
            client.execute('INSERT INTO clients_dimension VALUES', data, types_check=True)
            logging.info(f"🟢 Loaded {len(data)} clients")
    except Exception as e:
        logging.error(f"❌ Failed to load clients: {e}")
        raise
    finally:
        client.disconnect()


def load_devices_to_clickhouse(**context):
    client = ClickHouseClient(host='clickhouse', port=9000, user='admin', password='admin123', database='prosthetics_mart')
    try:
        data = context['ti'].xcom_pull(task_ids='extract_devices_data', key='devices_data')
        if data:
            client.execute('TRUNCATE TABLE devices_dimension')
            client.execute('INSERT INTO devices_dimension VALUES', data, types_check=True)
            logging.info(f"🟢 Loaded {len(data)} devices")
    except Exception as e:
        logging.error(f"❌ Failed to load devices: {e}")
        raise
    finally:
        client.disconnect()


def load_telemetry_to_clickhouse(**context):
    client = ClickHouseClient(host='clickhouse', port=9000, user='admin', password='admin123', database='prosthetics_mart')
    try:
        data = context['ti'].xcom_pull(task_ids='extract_telemetry_data', key='telemetry_data')
        if data:
            client.execute('INSERT INTO telemetry_landing VALUES', data, types_check=True)
            logging.info(f"🟢 Loaded {len(data)} telemetry records")
    except Exception as e:
        logging.error(f"❌ Failed to load telemetry: {e}")
        raise
    finally:
        client.disconnect()


# --- Backfill: Заполняем витрину вручную ---

def backfill_daily_mart(**context):
    """
    Полностью пересчитывает client_telemetry_daily_mart
    за последние 2 дня (или нужный период)
    """
    client = ClickHouseClient(host='clickhouse', port=9000, user='admin', password='admin123', database='prosthetics_mart')
    try:
        # Очищаем витрину (или фильтруем по периоду)
        # Вариант 1: полная очистка (если данных немного)
        client.execute('TRUNCATE TABLE client_telemetry_daily_mart')

        # Вариант 2: пересчёт за последние N дней (лучше для больших данных)
        # start_date = (datetime.now() - timedelta(days=2)).date()
        # client.execute(f"DELETE FROM client_telemetry_daily_mart WHERE period_date >= '{start_date}'")

        sql = '''
        INSERT INTO client_telemetry_daily_mart (
            client_id, external_client_id, client_name, email,
            device_id, device_name, device_type, period_date,
            telemetry_count,
            avg_battery_level, min_battery_level, max_battery_level,
            avg_temperature, max_temperature,
            avg_pressure, max_pressure,
            avg_flexion_angle, max_flexion_angle,
            total_steps, error_count, active_hours,
            first_telemetry_time, last_telemetry_time,
            avg_acceleration_magnitude, max_acceleration_magnitude, movement_intensity,
            has_low_battery, has_high_temperature, has_pressure_alert
        )
        SELECT 
            c.client_id,
            c.external_client_id,
            concat(c.first_name, ' ', c.last_name) AS client_name,
            c.email,
            d.device_id,
            coalesce(d.device_name, d.device_id) AS device_name,
            d.device_type,
            toDate(t.timestamp) AS period_date,

            count() AS telemetry_count,
            avg(t.battery_level), min(t.battery_level), max(t.battery_level),
            avg(t.temperature), max(t.temperature),
            avg(t.pressure_sensor_reading), max(t.pressure_sensor_reading),
            avg(t.flexion_angle), max(t.flexion_angle),
            sum(t.step_count),
            sum(if(t.error_code > 0, 1, 0)),
            countDistinct(toHour(t.timestamp)),

            min(t.timestamp), max(t.timestamp),

            avg(sqrt(power(t.accelerometer_x, 2) + power(t.accelerometer_y, 2) + power(t.accelerometer_z, 2))),
            max(sqrt(power(t.accelerometer_x, 2) + power(t.accelerometer_y, 2) + power(t.accelerometer_z, 2))),
            sum(if(sqrt(power(t.accelerometer_x, 2) + power(t.accelerometer_y, 2) + power(t.accelerometer_z, 2)) > 1.0, 1, 0)),

            if(min(t.battery_level) < 20, 1, 0),
            if(max(t.temperature) > 40, 1, 0),
            if(max(t.pressure_sensor_reading) > 50, 1, 0)

        FROM telemetry_landing t
        INNER JOIN devices_dimension d ON t.device_id = d.device_id
        INNER JOIN clients_dimension c ON d.client_id = c.client_id
        WHERE c.is_active = 1 AND d.is_active = 1
        GROUP BY 
            c.client_id, c.external_client_id, client_name, c.email,
            d.device_id, device_name, d.device_type,
            period_date
        '''

        client.execute(sql)
        logging.info("✅ Successfully backfilled client_telemetry_daily_mart")
    except Exception as e:
        logging.error(f"❌ Backfill failed: {e}")
        raise
    finally:
        client.disconnect()


# --- DAG ---

with DAG(
    'etl_prosthetics_to_clickhouse',
    default_args=default_args,
    description='ETL to ClickHouse without MV — manual mart backfill',
    catchup=False,
    tags=['etl', 'prosthetics', 'simple'],
    max_active_runs=1
) as dag:

    # Extraction
    extract_clients = PythonOperator(
        task_id='extract_clients_data',
        python_callable=extract_clients_data,
    )

    extract_devices = PythonOperator(
        task_id='extract_devices_data',
        python_callable=extract_devices_data,
    )

    extract_telemetry = PythonOperator(
        task_id='extract_telemetry_data',
        python_callable=extract_telemetry_data,
    )

    # Load
    load_clients = PythonOperator(
        task_id='load_clients_to_clickhouse',
        python_callable=load_clients_to_clickhouse,
    )

    load_devices = PythonOperator(
        task_id='load_devices_to_clickhouse',
        python_callable=load_devices_to_clickhouse,
    )

    load_telemetry = PythonOperator(
        task_id='load_telemetry_to_clickhouse',
        python_callable=load_telemetry_to_clickhouse,
    )

    # Backfill mart
    backfill_mart = PythonOperator(
        task_id='backfill_daily_mart',
        python_callable=backfill_daily_mart,
    )

    # Dependencies
    extract_clients >> load_clients
    extract_devices >> load_devices
    extract_telemetry >> load_telemetry

    [load_clients, load_devices] >> load_telemetry
    load_telemetry >> backfill_mart
