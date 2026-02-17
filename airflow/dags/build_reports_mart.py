from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import clickhouse_connect
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
    'execution_timeout': timedelta(minutes=25),
}


def check_source_data_availability(**context):
    logger.info("Checking source data availability")
    
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
        telemetry_count = client.query("SELECT count() FROM telemetry_raw")
        telemetry_records = telemetry_count.result_rows[0][0]
        logger.info(f"Telemetry records available: {telemetry_records}")
        
        crm_count = client.query("SELECT count() FROM crm_data")
        crm_records = crm_count.result_rows[0][0]
        logger.info(f"CRM records available: {crm_records}")
        
        if telemetry_records == 0:
            raise ValueError("No telemetry data available. Cannot build reports mart.")
        
        if crm_records == 0:
            raise ValueError("No CRM data available. Cannot build reports mart.")
        
        logger.info("Source data availability check passed")
        
        context['task_instance'].xcom_push(key='telemetry_count', value=telemetry_records)
        context['task_instance'].xcom_push(key='crm_count', value=crm_records)
        
    except Exception as e:
        logger.error(f"Error checking source data: {e}")
        raise
    finally:
        client.close()


def build_reports_mart(execution_date, **context):
    logger.info(f"Building reports mart for {execution_date}")
    
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
        build_mart_query = """
            INSERT INTO reports_mart (
                user_id,
                device_id,
                period_month,
                full_name,
                email,
                country,
                device_type,
                total_signals,
                avg_processing_time_ms,
                max_processing_time_ms,
                min_processing_time_ms,
                myo_signals_count,
                battery_checks_count,
                actuator_events_count,
                total_actions,
                most_frequent_action,
                action_frequency,
                device_status,
                warranty_until,
                data_freshness_date
            )
            SELECT 
                t.user_id,
                t.device_id,
                toStartOfMonth(t.timestamp) as period_month,
                
                -- Данные пользователя из CRM
                any(c.full_name) as full_name,
                any(c.email) as email,
                any(c.country) as country,
                any(c.device_type) as device_type,
                
                -- Агрегированные метрики телеметрии
                count() as total_signals,
                avg(t.processing_time_ms) as avg_processing_time_ms,
                max(t.processing_time_ms) as max_processing_time_ms,
                min(t.processing_time_ms) as min_processing_time_ms,
                
                -- Метрики по типам датчиков
                countIf(t.sensor_type = 'myo') as myo_signals_count,
                countIf(t.sensor_type = 'battery') as battery_checks_count,
                countIf(t.sensor_type = 'actuator') as actuator_events_count,
                
                -- Метрики по действиям
                countIf(t.action_executed != '') as total_actions,
                topK(1)(t.action_executed)[1] as most_frequent_action,
                countEqual(
                    groupArray(t.action_executed),
                    topK(1)(t.action_executed)[1]
                ) as action_frequency,
                
                -- Статус устройства из CRM
                any(c.device_status) as device_status,
                any(c.warranty_until) as warranty_until,
                
                -- Дата последних данных
                max(t.timestamp) as data_freshness_date
                
            FROM telemetry_raw t
            LEFT JOIN crm_data c ON t.user_id = c.user_id AND t.device_id = c.device_id
            WHERE toStartOfMonth(t.timestamp) >= toStartOfMonth(now()) - INTERVAL 12 MONTH
            GROUP BY t.user_id, t.device_id, period_month
            HAVING total_signals > 0
        """
        
        logger.info("Executing build_reports_mart query...")
        result = client.command(build_mart_query)
        logger.info(f"Build mart query executed successfully")
        
        count_query = "SELECT count() FROM reports_mart"
        count_result = client.query(count_query)
        total_reports = count_result.result_rows[0][0]
        logger.info(f"Total reports in mart: {total_reports}")
        
        recent_reports_query = """
            SELECT 
                period_month,
                count() as reports_count,
                sum(total_signals) as total_signals_sum
            FROM reports_mart
            WHERE period_month = toStartOfMonth(now())
            GROUP BY period_month
        """
        recent_stats = client.query(recent_reports_query)
        
        if recent_stats.result_rows:
            period, reports_count, signals_sum = recent_stats.result_rows[0]
            logger.info(f"Current month ({period}): {reports_count} reports, {signals_sum} total signals")
        
        context['task_instance'].xcom_push(key='total_reports', value=total_reports)
        
    except Exception as e:
        logger.error(f"Error building reports mart: {e}")
        raise
    finally:
        client.close()


def optimize_reports_mart(**context):
    logger.info("Optimizing reports_mart table")
    
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
        client.command("OPTIMIZE TABLE reports_mart FINAL")
        logger.info("Successfully optimized reports_mart table")
        
        size_query = """
            SELECT 
                formatReadableSize(sum(bytes)) as size,
                sum(rows) as rows
            FROM system.parts
            WHERE database = 'bionicpro' AND table = 'reports_mart' AND active
        """
        size_result = client.query(size_query)
        
        if size_result.result_rows:
            size, rows = size_result.result_rows[0]
            logger.info(f"reports_mart table size: {size}, rows: {rows}")
        
    except Exception as e:
        logger.error(f"Error optimizing reports_mart: {e}")
        logger.warning("Optimization failed, but continuing...")
    finally:
        client.close()


def verify_reports_quality(**context):
    logger.info("Verifying reports quality")
    
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
        missing_users_query = """
            SELECT countDistinct(t.user_id) as users_without_reports
            FROM telemetry_raw t
            LEFT JOIN reports_mart r ON t.user_id = r.user_id 
                AND t.device_id = r.device_id 
                AND toStartOfMonth(t.timestamp) = r.period_month
            WHERE r.user_id IS NULL
        """
        missing_result = client.query(missing_users_query)
        missing_users = missing_result.result_rows[0][0]
        
        if missing_users > 0:
            logger.warning(f"Found {missing_users} users with telemetry but no reports")
        else:
            logger.info("All users with telemetry have reports - check passed")
        
        invalid_metrics_query = """
            SELECT count() as invalid_reports
            FROM reports_mart
            WHERE total_signals = 0 
               OR avg_processing_time_ms < 0
               OR full_name = ''
               OR email = ''
        """
        invalid_result = client.query(invalid_metrics_query)
        invalid_reports = invalid_result.result_rows[0][0]
        
        if invalid_reports > 0:
            logger.warning(f"Found {invalid_reports} reports with invalid metrics")
        else:
            logger.info("All reports have valid metrics - check passed")
        
        freshness_query = """
            SELECT 
                min(data_freshness_date) as oldest_data,
                max(data_freshness_date) as newest_data,
                dateDiff('day', min(data_freshness_date), max(data_freshness_date)) as data_range_days
            FROM reports_mart
        """
        freshness_result = client.query(freshness_query)
        
        if freshness_result.result_rows:
            oldest, newest, range_days = freshness_result.result_rows[0]
            logger.info(f"Data freshness: oldest={oldest}, newest={newest}, range={range_days} days")
        
        logger.info("Reports quality verification completed")
        
    except Exception as e:
        logger.error(f"Error during quality verification: {e}")
        raise
    finally:
        client.close()


with DAG(
    'build_reports_mart',
    default_args=default_args,
    description='Построение витрины отчётов из телеметрии и CRM данных',
    schedule_interval='0 3 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['bionicpro', 'etl', 'reports', 'mart'],
    max_active_runs=1,
) as dag:
    
    check_data_task = PythonOperator(
        task_id='check_source_data',
        python_callable=check_source_data_availability,
        provide_context=True,
    )
    
    build_mart_task = PythonOperator(
        task_id='build_reports_mart',
        python_callable=build_reports_mart,
        provide_context=True,
    )
    
    optimize_task = PythonOperator(
        task_id='optimize_reports_mart',
        python_callable=optimize_reports_mart,
        provide_context=True,
    )
    
    verify_task = PythonOperator(
        task_id='verify_reports_quality',
        python_callable=verify_reports_quality,
        provide_context=True,
    )
    
    check_data_task >> build_mart_task >> optimize_task >> verify_task
