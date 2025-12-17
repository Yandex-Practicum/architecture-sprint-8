"""
ETL DAG для подготовки витрины отчётности BionicPRO
Объединяет данные телеметрии из PostgreSQL и данные клиентов из CRM
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.http.hooks.http import HttpHook
import logging

# Настройки подключений
POSTGRES_CONN_ID = 'postgres_default'
CRM_CONN_ID = 'crm_http'
CLICKHOUSE_CONN_ID = 'clickhouse_default'

# Параметры по умолчанию для DAG
default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2024, 1, 1),
}

# Создание DAG
dag = DAG(
    'reports_etl_dag',
    default_args=default_args,
    description='ETL процесс для подготовки витрины отчётности BionicPRO',
    schedule_interval='0 2 * * *',  # Ежедневно в 2:00 ночи
    catchup=False,
    tags=['bionicpro', 'etl', 'reports'],
)


def extract_telemetry_data(**context):
    """
    Извлекает данные телеметрии из PostgreSQL за последние 24 часа
    """
    postgres_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    
    # SQL запрос для извлечения агрегированных данных телеметрии
    sql = """
    SELECT 
        user_id,
        prosthesis_id,
        DATE(created_at) as report_date,
        COUNT(*) as total_actions,
        AVG(response_time_ms) as avg_response_time,
        MAX(response_time_ms) as max_response_time,
        MIN(response_time_ms) as min_response_time,
        COUNT(CASE WHEN action_type = 'grasp' THEN 1 END) as grasp_count,
        COUNT(CASE WHEN action_type = 'release' THEN 1 END) as release_count,
        COUNT(CASE WHEN action_type = 'flex' THEN 1 END) as flex_count,
        AVG(battery_level) as avg_battery_level,
        MIN(battery_level) as min_battery_level,
        SUM(duration_seconds) as total_usage_seconds
    FROM telemetry_data
    WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
      AND created_at < CURRENT_DATE
    GROUP BY user_id, prosthesis_id, DATE(created_at)
    ORDER BY user_id, report_date;
    """
    
    logging.info("Извлечение данных телеметрии из PostgreSQL...")
    
    try:
        df = postgres_hook.get_pandas_df(sql)
        
        if df.empty:
            logging.warning("Нет данных телеметрии за указанный период")
            context['ti'].xcom_push(key='telemetry_data', value=[])
            return 0
        
        # Сохраняем данные во временное хранилище (XCom)
        context['ti'].xcom_push(key='telemetry_data', value=df.to_dict('records'))
        
        logging.info(f"Извлечено {len(df)} записей телеметрии")
        return len(df)
    except Exception as e:
        logging.error(f"Ошибка при извлечении данных телеметрии: {str(e)}")
        context['ti'].xcom_push(key='telemetry_data', value=[])
        raise


def extract_crm_data(**context):
    """
    Извлекает данные клиентов из CRM системы через API
    """
    http_hook = HttpHook(http_conn_id=CRM_CONN_ID, method='GET')
    
    logging.info("Извлечение данных клиентов из CRM...")
    
    # Получаем список пользователей из CRM
    # В реальной реализации здесь будет вызов API CRM
    # Для примера используем заглушку
    try:
        response = http_hook.run(
            endpoint='/api/users',
            headers={'Content-Type': 'application/json'},
            extra_options={'timeout': 30}
        )
        
        if response.status_code == 200:
            users_data = response.json()
            logging.info(f"Получено {len(users_data)} пользователей из CRM")
            
            # Сохраняем данные в XCom
            context['ti'].xcom_push(key='crm_users_data', value=users_data)
            return len(users_data)
        else:
            logging.error(f"Ошибка при получении данных из CRM: {response.status_code}")
            raise Exception(f"CRM API вернул код {response.status_code}")
            
    except Exception as e:
        logging.error(f"Ошибка при извлечении данных из CRM: {str(e)}")
        # В случае ошибки используем заглушку для разработки
        logging.warning("Используются тестовые данные CRM")
        test_data = [
            {
                'user_id': 1,
                'email': 'user1@example.com',
                'first_name': 'User',
                'last_name': 'One',
                'prosthesis_id': 'PROT-001',
                'order_date': '2024-01-15',
                'status': 'active'
            }
        ]
        context['ti'].xcom_push(key='crm_users_data', value=test_data)
        return len(test_data)


def transform_and_join_data(**context):
    """
    Трансформирует и объединяет данные телеметрии и CRM
    """
    import pandas as pd
    
    # Получаем данные из предыдущих задач
    ti = context['ti']
    telemetry_records = ti.xcom_pull(key='telemetry_data', task_ids='extract_telemetry')
    crm_users = ti.xcom_pull(key='crm_users_data', task_ids='extract_crm_data')
    
    logging.info("Трансформация и объединение данных...")
    
    # Проверяем наличие данных
    if not telemetry_records:
        logging.warning("Нет данных телеметрии для обработки")
        return 0
    
    if not crm_users:
        logging.warning("Нет данных CRM для обработки")
        return 0
    
    # Преобразуем в DataFrame
    telemetry_df = pd.DataFrame(telemetry_records)
    crm_df = pd.DataFrame(crm_users)
    
    # Обрабатываем конфликт колонок: если prosthesis_id есть в обеих таблицах,
    # используем версию из телеметрии (более актуальную)
    if 'prosthesis_id' in crm_df.columns and 'prosthesis_id' in telemetry_df.columns:
        crm_df = crm_df.rename(columns={'prosthesis_id': 'prosthesis_id_crm'})
    
    # Объединяем данные по user_id
    # Используем left join, чтобы сохранить все записи телеметрии
    merged_df = telemetry_df.merge(
        crm_df,
        on='user_id',
        how='left',
        suffixes=('_telemetry', '_crm')
    )
    
    # Если prosthesis_id был переименован, используем версию из телеметрии
    if 'prosthesis_id_crm' in merged_df.columns:
        merged_df['prosthesis_id'] = merged_df.get('prosthesis_id', merged_df['prosthesis_id_crm'])
        merged_df = merged_df.drop(columns=['prosthesis_id_crm'], errors='ignore')
    
    # Добавляем вычисляемые поля
    merged_df['usage_hours'] = merged_df['total_usage_seconds'] / 3600.0
    merged_df['usage_hours'] = merged_df['usage_hours'].fillna(0)
    merged_df['actions_per_hour'] = merged_df.apply(
        lambda row: row['total_actions'] / row['usage_hours'] if row['usage_hours'] > 0 else 0,
        axis=1
    )
    merged_df['efficiency_score'] = merged_df['avg_response_time'].apply(
        lambda x: max(0.0, min(100.0, 100.0 - (x / 10.0))) if pd.notna(x) else 0.0
    )
    
    # Заполняем пропущенные значения
    merged_df['email'] = merged_df['email'].fillna('')
    merged_df['first_name'] = merged_df['first_name'].fillna('')
    merged_df['last_name'] = merged_df['last_name'].fillna('')
    merged_df['prosthesis_id'] = merged_df['prosthesis_id'].fillna('')
    merged_df['order_date'] = merged_df['order_date'].fillna('1970-01-01')
    merged_df['status'] = merged_df['status'].fillna('unknown')
    
    # Формируем финальную структуру витрины
    # Используем только существующие колонки
    available_columns = [
        'user_id', 'email', 'first_name', 'last_name', 'prosthesis_id',
        'report_date', 'total_actions', 'avg_response_time', 'max_response_time',
        'min_response_time', 'grasp_count', 'release_count', 'flex_count',
        'avg_battery_level', 'min_battery_level', 'total_usage_seconds',
        'usage_hours', 'actions_per_hour', 'efficiency_score', 'order_date', 'status'
    ]
    
    # Выбираем только существующие колонки
    existing_columns = [col for col in available_columns if col in merged_df.columns]
    data_mart = merged_df[existing_columns].copy()
    
    # Заполняем числовые значения нулями, если они отсутствуют
    numeric_columns = ['total_actions', 'avg_response_time', 'max_response_time', 
                      'min_response_time', 'grasp_count', 'release_count', 'flex_count',
                      'avg_battery_level', 'min_battery_level', 'total_usage_seconds',
                      'usage_hours', 'actions_per_hour', 'efficiency_score']
    for col in numeric_columns:
        if col in data_mart.columns:
            data_mart[col] = pd.to_numeric(data_mart[col], errors='coerce').fillna(0.0)
    
    # Сохраняем результат в XCom
    context['ti'].xcom_push(key='data_mart', value=data_mart.to_dict('records'))
    
    logging.info(f"Подготовлено {len(data_mart)} записей для витрины")
    return len(data_mart)


def load_to_clickhouse(**context):
    """
    Загружает данные в витрину ClickHouse
    """
    import clickhouse_connect
    import os
    from datetime import datetime, date
    
    ti = context['ti']
    data_mart_records = ti.xcom_pull(key='data_mart', task_ids='transform_data')
    
    if not data_mart_records:
        logging.warning("Нет данных для загрузки в ClickHouse")
        return 0
    
    logging.info(f"Загрузка {len(data_mart_records)} записей в ClickHouse...")
    
    # Подключение к ClickHouse
    # В реальной реализации используйте Airflow Connection или переменные окружения
    clickhouse_host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    clickhouse_port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
    clickhouse_user = os.getenv('CLICKHOUSE_USER', 'default')
    clickhouse_password = os.getenv('CLICKHOUSE_PASSWORD', '')
    clickhouse_database = os.getenv('CLICKHOUSE_DATABASE', 'bionicpro_reports')
    
    # Функция для преобразования строки в date
    def parse_date(date_value):
        """Преобразует строку или объект date в объект date"""
        if isinstance(date_value, date):
            return date_value
        if isinstance(date_value, datetime):
            return date_value.date()
        if isinstance(date_value, str):
            try:
                # Пробуем разные форматы даты
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d.%m.%Y']:
                    try:
                        return datetime.strptime(date_value, fmt).date()
                    except ValueError:
                        continue
                # Если не удалось распарсить, возвращаем дату по умолчанию
                logging.warning(f"Не удалось распарсить дату: {date_value}, используется дата по умолчанию")
                return date(1970, 1, 1)
            except Exception as e:
                logging.warning(f"Ошибка при парсинге даты {date_value}: {e}")
                return date(1970, 1, 1)
        return date(1970, 1, 1)
    
    try:
        client = clickhouse_connect.get_client(
            host=clickhouse_host,
            port=clickhouse_port,
            username=clickhouse_user,
            password=clickhouse_password,
            database=clickhouse_database
        )
        
        # Преобразуем данные в список кортежей для вставки
        data_to_insert = []
        for record in data_mart_records:
            data_to_insert.append([
                int(record['user_id']),
                str(record.get('email', '')),
                str(record.get('first_name', '')),
                str(record.get('last_name', '')),
                str(record.get('prosthesis_id', '')),
                parse_date(record.get('report_date')),
                int(record.get('total_actions', 0)),
                float(record['avg_response_time']) if record.get('avg_response_time') else 0.0,
                float(record['max_response_time']) if record.get('max_response_time') else 0.0,
                float(record['min_response_time']) if record.get('min_response_time') else 0.0,
                int(record.get('grasp_count', 0)),
                int(record.get('release_count', 0)),
                int(record.get('flex_count', 0)),
                float(record['avg_battery_level']) if record.get('avg_battery_level') else 0.0,
                float(record['min_battery_level']) if record.get('min_battery_level') else 0.0,
                int(record.get('total_usage_seconds', 0)),
                float(record['usage_hours']) if record.get('usage_hours') else 0.0,
                float(record['actions_per_hour']) if record.get('actions_per_hour') else 0.0,
                float(record['efficiency_score']) if record.get('efficiency_score') else 0.0,
                parse_date(record.get('order_date', '1970-01-01')),
                str(record.get('status', '')),
            ])
        
        # Выполняем вставку данных
        client.insert(
            'reports_data_mart',
            data_to_insert,
            column_names=[
                'user_id', 'email', 'first_name', 'last_name', 'prosthesis_id',
                'report_date', 'total_actions', 'avg_response_time', 'max_response_time',
                'min_response_time', 'grasp_count', 'release_count', 'flex_count',
                'avg_battery_level', 'min_battery_level', 'total_usage_seconds',
                'usage_hours', 'actions_per_hour', 'efficiency_score', 'order_date', 'status'
            ]
        )
        
        logging.info(f"Успешно загружено {len(data_to_insert)} записей в ClickHouse")
        return len(data_to_insert)
        
    except Exception as e:
        logging.error(f"Ошибка при загрузке данных в ClickHouse: {str(e)}")
        raise


# Определение задач DAG

# Задача 1: Извлечение данных телеметрии из PostgreSQL
extract_telemetry_task = PythonOperator(
    task_id='extract_telemetry',
    python_callable=extract_telemetry_data,
    dag=dag,
)

# Задача 2: Извлечение данных из CRM
extract_crm_task = PythonOperator(
    task_id='extract_crm_data',
    python_callable=extract_crm_data,
    dag=dag,
)

# Задача 3: Трансформация и объединение данных
transform_task = PythonOperator(
    task_id='transform_data',
    python_callable=transform_and_join_data,
    dag=dag,
)

def create_clickhouse_table(**context):
    """
    Создаёт таблицу витрины в ClickHouse, если она не существует
    """
    import clickhouse_connect
    import os
    
    clickhouse_host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    clickhouse_port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
    clickhouse_user = os.getenv('CLICKHOUSE_USER', 'default')
    clickhouse_password = os.getenv('CLICKHOUSE_PASSWORD', '')
    
    try:
        client = clickhouse_connect.get_client(
            host=clickhouse_host,
            port=clickhouse_port,
            username=clickhouse_user,
            password=clickhouse_password
        )
        
        # Создание базы данных
        client.command("CREATE DATABASE IF NOT EXISTS bionicpro_reports")
        
        # SQL для создания таблицы
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS bionicpro_reports.reports_data_mart (
            user_id UInt32,
            email String,
            first_name String,
            last_name String,
            prosthesis_id String,
            report_date Date,
            total_actions UInt32,
            avg_response_time Float32,
            max_response_time Float32,
            min_response_time Float32,
            grasp_count UInt32,
            release_count UInt32,
            flex_count UInt32,
            avg_battery_level Float32,
            min_battery_level Float32,
            total_usage_seconds UInt32,
            usage_hours Float32,
            actions_per_hour Float32,
            efficiency_score Float32,
            order_date Date,
            status String,
            created_at DateTime DEFAULT now(),
            updated_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(report_date)
        ORDER BY (user_id, report_date, prosthesis_id)
        PRIMARY KEY (user_id, report_date)
        SETTINGS index_granularity = 8192
        """
        
        client.command(create_table_sql)
        logging.info("Таблица витрины успешно создана или уже существует")
        
    except Exception as e:
        logging.error(f"Ошибка при создании таблицы: {str(e)}")
        raise


# Задача 4: Создание таблицы витрины (если не существует)
create_table_task = PythonOperator(
    task_id='create_data_mart_table',
    python_callable=create_clickhouse_table,
    dag=dag,
)

# Задача 5: Загрузка данных в ClickHouse
load_to_clickhouse_task = PythonOperator(
    task_id='load_to_clickhouse',
    python_callable=load_to_clickhouse,
    dag=dag,
)

# Определение зависимостей между задачами
[extract_telemetry_task, extract_crm_task] >> transform_task >> create_table_task >> load_to_clickhouse_task

