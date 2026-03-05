"""
BionicPRO · Airflow DAG · etl_reports
=====================================
ETL-процесс для построения витрины отчётов в ClickHouse.

Поток данных:
  1. Проверяем доступность источников (CRM PostgreSQL, ClickHouse)
  2. Очищаем витрину user_reports (full refresh)
  3. Строим витрину: ClickHouse читает телеметрию (emg_sensor_data)
     и делает JOIN с CRM через табличную функцию postgresql()
  4. Верифицируем результат (витрина не пустая)
  5. Очищаем кэш отчётов в S3 (задание 3: инвалидация после обновления витрины)

Расписание: @daily (каждую ночь в 00:00 UTC)
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

# ── Конфигурация подключений ────────────────────────────────────────────────
# В production — через Airflow Connections (Admin → Connections).
# Для учебного проекта — константы, совпадающие с docker-compose.yaml.

CLICKHOUSE_HOST = 'olap_db'
CLICKHOUSE_PORT = 9000

CRM_HOST = 'crm_db'
CRM_PORT = 5432
CRM_DB = 'crm_db'
CRM_USER = 'crm_user'
CRM_PASSWORD = 'crm_password'

MINIO_ENDPOINT = 'minio:9000'
MINIO_ACCESS_KEY = 'minio_user'
MINIO_SECRET_KEY = 'minio_password'
MINIO_BUCKET = 'reports'


# ── Task-функции ────────────────────────────────────────────────────────────

def check_sources(**context):
    """Проверяем, что ClickHouse и CRM PostgreSQL доступны."""
    from clickhouse_driver import Client as CHClient
    import psycopg2

    # ClickHouse
    ch = CHClient(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)
    result = ch.execute("SELECT 1")
    assert result == [(1,)], "ClickHouse health check failed"

    # Проверяем, что таблица телеметрии содержит данные
    count = ch.execute("SELECT count() FROM emg_sensor_data")
    sensor_rows = count[0][0]
    assert sensor_rows > 0, "emg_sensor_data is empty — нет данных телеметрии"

    # CRM PostgreSQL
    conn = psycopg2.connect(
        host=CRM_HOST, port=CRM_PORT,
        dbname=CRM_DB, user=CRM_USER, password=CRM_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM customers")
    crm_rows = cur.fetchone()[0]
    assert crm_rows > 0, "CRM customers table is empty"
    cur.close()
    conn.close()

    # Передаём метрики в XCom для логирования
    context['ti'].xcom_push(key='sensor_rows', value=sensor_rows)
    context['ti'].xcom_push(key='crm_rows', value=crm_rows)
    print(f"Sources OK: emg_sensor_data={sensor_rows} rows, customers={crm_rows} rows")


def truncate_view(**context):
    """Очищаем витрину перед полной перезагрузкой."""
    from clickhouse_driver import Client as CHClient

    ch = CHClient(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)
    ch.execute("TRUNCATE TABLE IF EXISTS user_reports")
    print("Витрина user_reports очищена")


def build_report_view(**context):
    """
    Строим витрину: JOIN телеметрии с CRM-данными.

    ClickHouse сам читает из CRM PostgreSQL через табличную функцию postgresql().
    Данные не проходят через Python — это эффективнее и проще.
    """
    from clickhouse_driver import Client as CHClient

    ch = CHClient(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)

    query = f"""
        INSERT INTO user_reports (
            user_id,
            customer_name,
            customer_email,
            prosthesis_type,
            total_signals,
            avg_amplitude,
            avg_frequency,
            avg_duration,
            min_signal_time,
            max_signal_time,
            report_updated
        )
        SELECT
            e.user_id                       AS user_id,
            coalesce(c.name, 'Unknown')     AS customer_name,
            coalesce(c.email, '')           AS customer_email,
            e.prosthesis_type               AS prosthesis_type,
            count()                         AS total_signals,
            round(avg(e.signal_amplitude), 2) AS avg_amplitude,
            round(avg(e.signal_frequency), 0) AS avg_frequency,
            round(avg(e.signal_duration), 0)  AS avg_duration,
            min(e.signal_time)              AS min_signal_time,
            max(e.signal_time)              AS max_signal_time,
            now()                           AS report_updated
        FROM emg_sensor_data AS e
        LEFT JOIN postgresql(
            '{CRM_HOST}:{CRM_PORT}',
            '{CRM_DB}',
            'customers',
            '{CRM_USER}',
            '{CRM_PASSWORD}'
        ) AS c ON e.user_id = toUInt32(c.id)
        GROUP BY
            e.user_id,
            c.name,
            c.email,
            e.prosthesis_type
        ORDER BY
            e.user_id,
            e.prosthesis_type
    """

    ch.execute(query)
    print("Витрина user_reports построена")


def verify_view(**context):
    """Проверяем, что витрина заполнена корректно."""
    from clickhouse_driver import Client as CHClient

    ch = CHClient(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT)

    # Общее количество записей
    total = ch.execute("SELECT count() FROM user_reports")[0][0]
    assert total > 0, "Витрина user_reports пуста после ETL!"

    # Количество уникальных пользователей
    users = ch.execute("SELECT uniq(user_id) FROM user_reports")[0][0]

    # Диапазон дат
    dates = ch.execute("""
        SELECT
            min(min_signal_time),
            max(max_signal_time)
        FROM user_reports
    """)[0]

    # Пример записи
    sample = ch.execute("""
        SELECT user_id, customer_name, prosthesis_type,
               total_signals, avg_amplitude
        FROM user_reports
        ORDER BY total_signals DESC
        LIMIT 3
    """)

    # Передаём метрики
    context['ti'].xcom_push(key='view_rows', value=total)
    context['ti'].xcom_push(key='view_users', value=users)

    print(f"Витрина OK:")
    print(f"  Записей:       {total}")
    print(f"  Пользователей: {users}")
    print(f"  Период:        {dates[0]} — {dates[1]}")
    print(f"  Топ-3 по количеству сигналов:")
    for row in sample:
        print(f"    user={row[0]}, name={row[1]}, type={row[2]}, "
              f"signals={row[3]}, avg_amp={row[4]}")


def invalidate_s3_cache(**context):
    """Очищаем кэш отчётов в S3 после обновления витрины.

    После перестроения витрины старые отчёты в S3 содержат устаревшие данные.
    Удаляем все объекты из bucket 'reports' — при следующем запросе пользователя
    Report Service сгенерирует свежий отчёт из обновлённой витрины.
    """
    from minio import Minio

    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )

    # Проверяем, что bucket существует
    if not client.bucket_exists(MINIO_BUCKET):
        print(f"Bucket '{MINIO_BUCKET}' не существует, пропускаем очистку")
        return

    # Удаляем все объекты
    objects = client.list_objects(MINIO_BUCKET, recursive=True)
    deleted = 0
    for obj in objects:
        client.remove_object(MINIO_BUCKET, obj.object_name)
        deleted += 1

    context['ti'].xcom_push(key='s3_deleted', value=deleted)
    print(f"S3 кэш очищен: удалено {deleted} объектов из bucket '{MINIO_BUCKET}'")


# ── DAG ─────────────────────────────────────────────────────────────────────

default_args = {
    'owner': 'bionicpro',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='etl_reports',
    default_args=default_args,
    description='ETL: CRM + телеметрия → витрина отчётов в ClickHouse',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['etl', 'reports', 'clickhouse'],
) as dag:

    t_check = PythonOperator(
        task_id='check_sources',
        python_callable=check_sources,
    )

    t_truncate = PythonOperator(
        task_id='truncate_view',
        python_callable=truncate_view,
    )

    t_build = PythonOperator(
        task_id='build_report_view',
        python_callable=build_report_view,
    )

    t_verify = PythonOperator(
        task_id='verify_view',
        python_callable=verify_view,
    )

    t_invalidate_s3 = PythonOperator(
        task_id='invalidate_s3_cache',
        python_callable=invalidate_s3_cache,
    )

    # Зависимости: линейная цепочка
    t_check >> t_truncate >> t_build >> t_verify >> t_invalidate_s3
