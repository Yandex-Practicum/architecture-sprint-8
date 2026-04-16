from datetime import datetime, timedelta, date
from airflow import DAG
from airflow.operators.python import PythonOperator
import psycopg2
from psycopg2.extras import RealDictCursor
from clickhouse_driver import Client
import logging
import json
from decimal import Decimal

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

def json_serializer(obj):
    """Сериализация специальных типов в JSON"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def extract_crm(**context):
    """Извлечение данных из CRM PostgreSQL"""
    logger.info("Начало извлечения данных из CRM")
    
    try:
        conn = psycopg2.connect(
            host='postgres_crm',
            port=5432,
            database='crm_db',
            user='crm_user',
            password='crm_password'
        )
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        SELECT 
            u.id::text as user_id,
            u.email,
            CONCAT(u.first_name, ' ', u.last_name) as user_name,
            u.country,
            p.id::text as prosthesis_id,
            p.prosthesis_type,
            p.last_tuning_date,
            p.tuning_count,
            p.manufacture_date
        FROM crm.users u
        INNER JOIN crm.prostheses p ON u.id = p.user_id
        WHERE p.status = 'active'
        """
        
        cur.execute(query)
        crm_data = cur.fetchall()
        
        logger.info(f"Извлечено {len(crm_data)} записей из CRM")
        
        cur.close()
        conn.close()
        
        # Ключевое исправление: default=str
        context['task_instance'].xcom_push(key='crm_data', value=json.dumps(crm_data, default=str))
        return len(crm_data)
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении из CRM: {e}")
        raise

def extract_telemetry(**context):
    """Извлечение данных телеметрии"""
    logger.info("Начало извлечения данных телеметрии")
    
    try:
        conn = psycopg2.connect(
            host='postgres_telemetry',
            port=5432,
            database='telemetry_db',
            user='telemetry_user',
            password='telemetry_password'
        )
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        from airflow.models import Variable
        last_load = Variable.get("last_telemetry_load", default_var=None)
        
        if not last_load:
            last_load = (date(2025,1,1)).strftime('%Y-%m-%d')
        
        query = f"""
        SELECT 
            user_id::text as user_id,
            prosthesis_id::text as prosthesis_id,
            timestamp,
            reaction_time_ms,
            movement_type,
            is_successful,
            battery_level,
            signal_quality
        FROM telemetry.raw_signals
        WHERE timestamp >= '{last_load}'
        ORDER BY user_id, timestamp
        """
        
        cur.execute(query)
        telemetry_data = cur.fetchall()
        
        logger.info(f"Извлечено {len(telemetry_data)} записей телеметрии")
        
        cur.close()
        conn.close()
        
        # Ключевое исправление: default=str
        context['task_instance'].xcom_push(key='telemetry_data', value=json.dumps(telemetry_data, default=str))
        context['task_instance'].xcom_push(key='extraction_date', value=datetime.now().isoformat())
        
        return len(telemetry_data)
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении из Telemetry: {e}")
        raise

def transform_and_aggregate(**context):
    """Трансформация и агрегация данных"""
    logger.info("Начало трансформации данных")
    
    ti = context['task_instance']
    
    crm_json = ti.xcom_pull(key='crm_data', task_ids='extract_crm')
    telemetry_json = ti.xcom_pull(key='telemetry_data', task_ids='extract_telemetry')
    
    if not crm_json or not telemetry_json:
        logger.error("Нет данных для трансформации")
        return None
    
    crm_data = json.loads(crm_json)
    telemetry_data = json.loads(telemetry_json)
    
    if not telemetry_data:
        logger.warning("Нет данных телеметрии")
        return None
    
    # Создание словаря CRM данных
    crm_dict = {}
    for crm in crm_data:
        key = f"{crm['user_id']}_{crm['prosthesis_id']}"
        crm_dict[key] = crm
    
    # Группировка телеметрии
    grouped = {}
    
    for signal in telemetry_data:
        # Фильтрация выбросов
        if signal['reaction_time_ms'] < 20 or signal['reaction_time_ms'] > 500:
            continue
        
        user_id = signal['user_id']
        prosthesis_id = signal['prosthesis_id']
        timestamp = signal['timestamp']
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        report_date = timestamp.date()
        
        key = f"{user_id}_{prosthesis_id}_{report_date}"
        
        if key not in grouped:
            grouped[key] = {
                'user_id': user_id,
                'prosthesis_id': prosthesis_id,
                'report_date': report_date.isoformat(),
                'first_signal_time': timestamp,
                'last_signal_time': timestamp,
                'total_signals': 0,
                'reaction_times': [],
                'successful_count': 0,
                'battery_levels': [],
                'signal_qualities': []
            }
        
        g = grouped[key]
        g['total_signals'] += 1
        
        if signal['is_successful']:
            g['successful_count'] += 1
        
        g['reaction_times'].append(signal['reaction_time_ms'])
        
        if signal.get('battery_level'):
            g['battery_levels'].append(signal['battery_level'])
        
        if signal.get('signal_quality'):
            g['signal_qualities'].append(float(signal['signal_quality']))
        
        if timestamp < g['first_signal_time']:
            g['first_signal_time'] = timestamp
        if timestamp > g['last_signal_time']:
            g['last_signal_time'] = timestamp
    
    # Формирование результата
    result_data = []
    
    for key, g in grouped.items():
        reaction_times = g['reaction_times']
        avg_reaction = sum(reaction_times) / len(reaction_times) if reaction_times else 0
        max_reaction = max(reaction_times) if reaction_times else 0
        min_reaction = min(reaction_times) if reaction_times else 0
        
        if len(reaction_times) > 1:
            variance = sum((x - avg_reaction) ** 2 for x in reaction_times) / len(reaction_times)
            stddev_reaction = variance ** 0.5
        else:
            stddev_reaction = 0
        
        successful = g['successful_count']
        total = g['total_signals']
        success_rate = successful / total if total > 0 else 0
        misclassification_rate = 1 - success_rate
        
        avg_battery = sum(g['battery_levels']) / len(g['battery_levels']) if g['battery_levels'] else 0
        min_battery = min(g['battery_levels']) if g['battery_levels'] else 0
        avg_signal_quality = sum(g['signal_qualities']) / len(g['signal_qualities']) if g['signal_qualities'] else 0
        
        quality_ok = 1 if avg_reaction <= 100 else 0
        needs_tuning = 1 if (avg_reaction > 100 or misclassification_rate > 0.3) else 0
        
        crm_key = f"{g['user_id']}_{g['prosthesis_id']}"
        crm = crm_dict.get(crm_key, {})
        
        result_data.append({
            'user_id': g['user_id'],
            'user_email': crm.get('email', 'unknown@example.com'),
            'user_name': crm.get('user_name', 'Unknown User'),
            'country': crm.get('country', 'Unknown'),
            'prosthesis_id': g['prosthesis_id'],
            'prosthesis_type': crm.get('prosthesis_type', 'standard'),
            'report_date': g['report_date'],
            'first_signal_time': g['first_signal_time'].isoformat(),
            'last_signal_time': g['last_signal_time'].isoformat(),
            'total_signals': total,
            'avg_reaction_time_ms': round(avg_reaction, 2),
            'max_reaction_time_ms': int(max_reaction),
            'min_reaction_time_ms': int(min_reaction),
            'stddev_reaction_time_ms': round(stddev_reaction, 2),
            'successful_movements': successful,
            'failed_movements': total - successful,
            'success_rate': round(success_rate, 3),
            'misclassification_rate': round(misclassification_rate, 3),
            'avg_battery_level': round(avg_battery, 1),
            'min_battery_level': int(min_battery),
            'avg_signal_quality': round(avg_signal_quality, 2),
            'quality_ok': quality_ok,
            'needs_tuning': needs_tuning,
            'tuning_count': crm.get('tuning_count', 0),
            'last_tuning_date': crm.get('last_tuning_date'),
            'prosthesis_age_days': 0
        })
    
    logger.info(f"Сформировано {len(result_data)} агрегированных записей")
    
    context['task_instance'].xcom_push(key='report_data', value=json.dumps(result_data, default=str))
    
    return len(result_data)

def load_to_clickhouse(**context):
    """Загрузка данных в ClickHouse"""
    logger.info("Начало загрузки в ClickHouse")
    
    ti = context['task_instance']
    report_json = ti.xcom_pull(key='report_data', task_ids='transform_and_aggregate')
    
    if not report_json:
        logger.warning("Нет данных для загрузки")
        return
    
    report_data = json.loads(report_json)
    
    if not report_data:
        logger.warning("Пустые данные")
        return
    
    try:
        client = Client(host='clickhouse', port=9000, user='default', password='')
        
        # Создание базы и таблицы
        client.execute("CREATE DATABASE IF NOT EXISTS bionicpro")
        client.execute("""
        CREATE TABLE IF NOT EXISTS bionicpro.user_report_mart (
            user_id String,
            user_email String,
            user_name String,
            country String,
            prosthesis_id String,
            prosthesis_type String,
            report_date Date,
            first_signal_time DateTime,
            last_signal_time DateTime,
            total_signals UInt32,
            avg_reaction_time_ms Float32,
            max_reaction_time_ms UInt32,
            min_reaction_time_ms UInt32,
            stddev_reaction_time_ms Float32,
            successful_movements UInt32,
            failed_movements UInt32,
            success_rate Float32,
            misclassification_rate Float32,
            avg_battery_level Float32,
            min_battery_level UInt8,
            avg_signal_quality Float32,
            quality_ok UInt8,
            needs_tuning UInt8,
            tuning_count UInt32,
            last_tuning_date DateTime,
            prosthesis_age_days UInt32,
            etl_created_at DateTime
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(report_date)
        ORDER BY (user_id, report_date)
        """)

        
        # Вставка данных
        records = []
        for row in report_data:
                    

            records.append({
                'user_id': row['user_id'],
                'user_email': row['user_email'],
                'user_name': row['user_name'],
                'country': row['country'],
                'prosthesis_id': row['prosthesis_id'],
                'prosthesis_type': row['prosthesis_type'],
                'report_date': datetime.strptime(row['report_date'], '%Y-%m-%d'),
                'first_signal_time':  datetime.strptime(row['first_signal_time'], '%Y-%m-%dT%H:%M:%S'),
                'last_signal_time': datetime.strptime(row['last_signal_time'],'%Y-%m-%dT%H:%M:%S'),
                'total_signals': row['total_signals'],
                'avg_reaction_time_ms': row['avg_reaction_time_ms'],
                'max_reaction_time_ms': row['max_reaction_time_ms'],
                'min_reaction_time_ms': row['min_reaction_time_ms'],
                'stddev_reaction_time_ms': row['stddev_reaction_time_ms'],
                'successful_movements': row['successful_movements'],
                'failed_movements': row['failed_movements'],
                'success_rate': row['success_rate'],
                'misclassification_rate': row['misclassification_rate'],
                'avg_battery_level': row['avg_battery_level'],
                'min_battery_level': row['min_battery_level'],
                'avg_signal_quality': row['avg_signal_quality'],
                'quality_ok': row['quality_ok'],
                'needs_tuning': row['needs_tuning'],
                'tuning_count': row['tuning_count'],
                'last_tuning_date': datetime.strptime(row['last_tuning_date'] or '2000-01-01 00:00:00', '%Y-%m-%d %H:%M:%S'),
                'prosthesis_age_days': row['prosthesis_age_days'],
                'etl_created_at': datetime.now()
            })
        
        batch_size = 100
        inserted = 0
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            logger.info(f"Я ТУТ")
            client.execute("INSERT INTO bionicpro.user_report_mart VALUES", batch)
            inserted += len(batch)
            logger.info(f"Загружено {inserted} из {len(records)}")
        
        client.disconnect()
        logger.info(f"Загрузка завершена. Всего записей: {inserted}")
        
        from airflow.models import Variable
        Variable.set("last_telemetry_load", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
    except Exception as e:
        logger.error(f"Ошибка загрузки в ClickHouse: {e}")
        raise

# Определение DAG
dag = DAG(
    'bionicpro_etl_postgres_mvp',
    default_args=DEFAULT_ARGS,
    description='ETL процесс из PostgreSQL в ClickHouse',
    schedule_interval='0 */6 * * *',
    catchup=False,
    max_active_runs=1,
)

extract_crm_task = PythonOperator(
    task_id='extract_crm',
    python_callable=extract_crm,
    provide_context=True,
    dag=dag,
)

extract_telemetry_task = PythonOperator(
    task_id='extract_telemetry',
    python_callable=extract_telemetry,
    provide_context=True,
    dag=dag,
)

transform_task = PythonOperator(
    task_id='transform_and_aggregate',
    python_callable=transform_and_aggregate,
    provide_context=True,
    dag=dag,
)

load_task = PythonOperator(
    task_id='load_to_clickhouse',
    python_callable=load_to_clickhouse,
    provide_context=True,
    dag=dag,
)

[extract_crm_task, extract_telemetry_task] >> transform_task >> load_task