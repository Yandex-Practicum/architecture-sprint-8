from datetime import datetime, timedelta
import logging

# The DAG object; we'll need this to instantiate a DAG
from airflow.models.dag import DAG
from airflow.decorators import dag, task
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow_clickhouse_plugin.hooks.clickhouse import ClickHouseHook
from airflow.models import Variable

task_logger = logging.getLogger("airflow.task")

# Функция-обработчик для превращения результата SQL в список словарей
def dict_handler(cursor):
    if cursor.description is None:
        return None
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@dag(
     description="Bionic DAG, collecting data from CRM DB and PROSTHESIS DB, and ingesting it into clickhouse datamart",
     start_date=datetime(2026, 4, 5), 
     schedule=timedelta(minutes=1), 
     catchup=False,
     tags=["practicum", "sprint9"],
     default_args={
        "depends_on_past": True,
        })
def bionic_dag():
  def load_users_pre_execute(context):
    task_logger.info("launched task for loading users from CRM DB...")
      # Fetch a simple string variable
    users_max_update_datetime = Variable.get("users_max_update_datetime", '2026-01-01 00:00:00')
    task_logger.info(f"Variable 'users_max_update_datetime': {users_max_update_datetime}")
  

  def load_users_post_execute(context, result):
    task_logger.info(f"Got {len(result)} items.")
    if not result:
        task_logger.info("No new items to update Variable.")
        return
    try:
        new_max_dt = max(row['updated_at'] for row in result)
        
        # Обновляем переменную Airflow
        Variable.set("users_max_update_datetime", new_max_dt)
        task_logger.info(f"Variable 'users_max_update_datetime' updated to: {new_max_dt}")
    except KeyError:
        task_logger.error("Column 'updated_at' not found in result set!")  
    
  bionic_crm_execution = SQLExecuteQueryOperator(
    task_id="load_users",
    conn_id="bionic_crm",
    depends_on_past=False,
    handler=dict_handler,
    sql="SELECT * FROM users WHERE updated_at > '{{ var.value.get('users_max_update_datetime', '2026-01-01 00:00:00') }}';",
    pre_execute=load_users_pre_execute,
    post_execute=load_users_post_execute
  )
  
  def load_prosthesis_usage_pre_execute(context):
    task_logger.info("launched task for loading prosthesis usage from API DB...")
      # Fetch a simple string variable
    usage_max_update_datetime = Variable.get("usage_max_update_datetime", '2026-01-01 00:00:00')
    context['ti'].xcom_push(key='usage_max_update_datetime', value=usage_max_update_datetime)
    task_logger.info(f"Variable 'usage_max_update_datetime': {usage_max_update_datetime}")
    


  def load_prosthesis_usage_post_execute(context, result):
    task_logger.info(f"Got {len(result)} items.")
    if not result:
        task_logger.info("No new items to update Variable.")
        return
    try:
        new_max_dt = max(row['end_time'] for row in result)
        
        # Обновляем переменную Airflow
        Variable.set("usage_max_update_datetime", new_max_dt)
        task_logger.info(f"Variable 'usage_max_update_datetime' updated to: {new_max_dt}")
    except KeyError:
        task_logger.error("Column 'end_time' not found in result set!")  
  
  prosthesis_usage_data_daily = SQLExecuteQueryOperator(
      task_id="load_prosthesis_usage",
      conn_id="bionic_prosthesis",
      depends_on_past=True,
      handler=dict_handler,
      sql="SELECT * FROM prosthesis_usage WHERE start_time > '2023-10-01 08:00:00' AND end_time > '{{  var.value.get('usage_max_update_datetime', '2026-01-01 00:00:00') }}'",
      pre_execute=load_prosthesis_usage_pre_execute,
      post_execute=load_prosthesis_usage_post_execute
    )
      
  @task 
  def join_results(users, usage_data):
    task_logger.info("launched task for joining results...")
    if not users or not usage_data:
      task_logger.info("One of the datasets is empty. Skipping join.")
      return []
    users_dict = {u["id"]: u for u in users}
    
    joined = []
    for usage in usage_data:
      user_id = usage.get("user_id")
      if user_id in users_dict:
         user = users_dict[user_id]
         joined.append({
                    "user_id": user_id,
                    "user_first_name": user.get("first_name"),
                    "user_last_name": user.get("last_name"),
                    "user_email": user.get("email"),
                    "event_start_time": usage.get("start_time"),
                    "event_end_time": usage.get("end_time"),
                    "movement_type": usage.get("movement_type"),
                    "movements_count": usage.get("movements_count")
                })
    if len(joined) > 0:
      task_logger.info("data arrays joined")
      task_logger.info(f"result data array len is {len(joined)}.")
    else:
      task_logger.info("EMPTY JOIN")
    return joined
        
  @task 
  def ingest_results(data):
    if not data:
        task_logger.info("No data to ingest.")
        return
    
    task_logger.info(f"Launched task for ingesting {len(data)} items to ClickHouse...")
    
    # Инициализируем Hook через clickhouse_conn_id
    hook = ClickHouseHook(clickhouse_conn_id="bionic_datamart")
    
    # Подготавливаем данные в виде списка кортежей для вставки
    values = [(
      row['event_start_time'], 
      row['event_end_time'], 
      row['movement_type'],
      row['movements_count'],
      row['user_id'],
      row['user_first_name'],
      row['user_last_name'],
      row['user_email'],
      ) for row in data]
    
    columns="event_start_time, event_end_time, movement_type, movements_count, user_id, user_first_name, user_last_name, user_email"
    
    hook.execute(
        sql=f"INSERT INTO prosthesis_events_datamart ({columns}) VALUES",
        params=values
    )
    
    task_logger.info("Data successfully ingested to ClickHouse via plugin hook.")
    
    items_count = hook.execute(sql=f"SELECT COUNT(*) FROM prosthesis_events_datamart")
    
    task_logger.info(f"There are {items_count[0][0]} items in table now")
    
    
    return True
  
  data = join_results(bionic_crm_execution.output, prosthesis_usage_data_daily.output)
  ingest_results(data)

bionic_dag()