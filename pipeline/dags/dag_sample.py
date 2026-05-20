from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime
import csv

# Аргументы по умолчанию: владелец процесса и время отсчета для задачи
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 12, 1),
}

# Функция для чтения данные и генерации SQL запросов
def generate_insert_queries():
    CSV_FILE_PATH = 'sample_files/sample.csv'
    with open( CSV_FILE_PATH, 'r') as csvfile:
        csvreader = csv.reader(csvfile)
    
        # Генерим запросы
        insert_queries = []
        is_header = True
        for row in csvreader:
            if is_header:
                is_header = False
                continue
            insert_query = f"INSERT INTO sample_table (id,order_number,total,discount,buyer_id) VALUES ({row[0]}, {row[1]}, {row[2]},{row[3]},{row[4]});"
            insert_queries.append(insert_query)
        
        # Сохраняем запросы
        with open('./dags/sql/insert_queries.sql', 'w') as f:
            for query in insert_queries:
                f.write(f"{query}\n")


# Определяем DAG
with DAG('csv_to_postgres_dag',
         default_args=default_args, #аргументы по умолчанию в начале скрипта
         schedule_interval='@once', #запускаем один раз
         catchup=False) as dag: #предотвращает повторное выполнение DAG для пропущенных расписаний.

    # Создаем таблицу в PostgreSQL
    create_table = PostgresOperator(
        task_id='create_table', #идентификатор задачи
        postgres_conn_id='write_to_postgres',  # Название подключения
        sql="""
        DROP TABLE IF EXISTS sample_table;
        CREATE TABLE sample_table (
            id SERIAL PRIMARY KEY,
            order_number BIGINT,
            total NUMERIC(18,2),
            discount NUMERIC(18,2),
            buyer_id BIGINT
        );
        """
    )
    #Опеределяем оператор для вставки данных
    generate_queries = PythonOperator(
    task_id='generate_insert_queries',
    python_callable=generate_insert_queries
    )

    #Запускаем выполнение оператора PostgresOperator
    run_insert_queries = PostgresOperator(
        task_id='run_insert_queries',
        postgres_conn_id='write_to_postgres',  # Название подключения к PostgreSQL в Airflow UI
        sql='sql/insert_queries.sql'
    )
    create_table>>generate_queries>>run_insert_queries
    # Тут дальше можно продолжать пайплайн