from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime
import csv

# Аргументы по умолчанию: владелец процесса и время отсчета для задачи
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2026, 5, 20),
}

postgres_conn_id='write_to_postgres'

# Функция для чтения данные и генерации SQL запросов
def generate_sales_insert_queries():
    CSV_FILE_PATH = 'data/sales.csv'
    with open( CSV_FILE_PATH, 'r') as csvfile:
        csvreader = csv.reader(csvfile)
    
        # Генерим запросы
        insert_queries = []
        is_header = True
        for row in csvreader:
            if is_header:
                is_header = False
                continue
            insert_query = f"INSERT INTO sales (id,order_number,total,discount,buyer_id) VALUES ({row[0]}, {row[1]}, {row[2]},{row[3]},{row[4]});"
            insert_queries.append(insert_query)
        
        # Сохраняем запросы
        with open('./dags/sql/sales_insert_queries.sql', 'w') as f:
            for query in insert_queries:
                f.write(f"{query}\n")


# Функция для чтения данные и генерации SQL запросов
def generate_telemetry_insert_queries():
    CSV_FILE_PATH = 'data/telemetry.csv'
    with open( CSV_FILE_PATH, 'r') as csvfile:
        csvreader = csv.reader(csvfile)
    
        # Генерим запросы
        insert_queries = []
        is_header = True
        for row in csvreader:
            if is_header:
                is_header = False
                continue
            insert_query = f"INSERT INTO telemetry (id,buyer_id,sensor_type,value,power) VALUES ({row[0]}, {row[1]}, {row[2]},{row[3]},{row[4]});"
            insert_queries.append(insert_query)
        
        # Сохраняем запросы
        with open('./dags/sql/telemetry_insert_queries.sql', 'w') as f:
            for query in insert_queries:
                f.write(f"{query}\n")


# Определяем DAG
with DAG('csv_to_postgres_dag',
         default_args=default_args, #аргументы по умолчанию в начале скрипта
         schedule_interval='@once', #запускаем один раз
         catchup=False) as dag: #предотвращает повторное выполнение DAG для пропущенных расписаний.

    # Создаем таблицу sales в PostgreSQL
    create_sales_table = PostgresOperator(
        task_id='create_sales_table', #идентификатор задачи
        postgres_conn_id=postgres_conn_id,  # Название подключения
        sql="""
        DROP TABLE IF EXISTS sales;
        CREATE TABLE sales (
            id SERIAL PRIMARY KEY,
            order_number BIGINT,
            total NUMERIC(18,2),
            discount NUMERIC(18,2),
            buyer_id BIGINT
        );
        """
    )

    # Создаем таблицу telemetry в PostgreSQL
    create_telemetry_table = PostgresOperator(
        task_id='create_telemetry_table', #идентификатор задачи
        postgres_conn_id=postgres_conn_id,  # Название подключения
        sql="""
        DROP TABLE IF EXISTS telemetry;
        CREATE TABLE telemetry (
            id SERIAL PRIMARY KEY,
            buyer_id BIGINT,
            sensor_type VARCHAR(255),
            value NUMERIC(18,2),
            power NUMERIC(18,2)
        );
        """
    )

    # Создаем таблицу buyer_summary_report в PostgreSQL
    create_buyer_summary_report_table = PostgresOperator(
        task_id='create_buyer_summary_report_table', #идентификатор задачи
        postgres_conn_id=postgres_conn_id,  # Название подключения
        sql="""
        DROP TABLE IF EXISTS buyer_summary_report;
        CREATE TABLE buyer_summary_report (
            buyer_id BIGINT,
            total_orders BIGINT,
            total_spent NUMERIC(18,2),
            total_discount NUMERIC(18,2),
            avg_sensor_value NUMERIC(18,2),
            max_power NUMERIC(18,2)
        );
        """
    )

    #Опеределяем оператор для вставки данных
    generate_sales_queries = PythonOperator(
        task_id="generate_sales_insert_queries",
        python_callable=generate_sales_insert_queries,
    )
    generate_telemetry_queries = PythonOperator(
        task_id="generate_telemetry_insert_queries",
        python_callable=generate_telemetry_insert_queries,
    )


    #Запускаем выполнение оператора PostgresOperator
    run_sales_insert_queries = PostgresOperator(
        task_id="run_sales_insert_queries",
        postgres_conn_id=postgres_conn_id,
        sql="sql/sales_insert_queries.sql",
    )
    run_telemetry_insert_queries = PostgresOperator(
        task_id="run_telemetry_insert_queries",
        postgres_conn_id=postgres_conn_id,
        sql="sql/telemetry_insert_queries.sql",
    )

    run_buyer_summary_report_insert_queries = PostgresOperator(
        task_id="run_buyer_summary_report_insert_queries",
        postgres_conn_id=postgres_conn_id,
        sql="sql/buyer_summary_report_insert_queries.sql",
    )

    result = (
        create_sales_table
        >>create_telemetry_table
        >>create_buyer_summary_report_table
        >>generate_sales_queries
        >>generate_telemetry_queries
        >>run_sales_insert_queries
        >>run_telemetry_insert_queries
        >>run_buyer_summary_report_insert_queries)
