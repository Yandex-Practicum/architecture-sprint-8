#!/bin/bash
# airflow/entrypoint.sh

set -e  # Останавливать выполнение при любой ошибке

echo "========================================="
echo "Airflow Entrypoint Script"
echo "========================================="

# Функция для проверки подключения к БД
wait_for_db() {
    echo "Checking database connection to $DB_HOST:$DB_PORT..."

    python -c "
import psycopg2
import time
import sys
import os

host = os.environ.get('DB_HOST', 'airflow_db')
port = int(os.environ.get('DB_PORT', 5432))
user = os.environ.get('DB_USER', 'airflow')
password = os.environ.get('DB_PASSWORD', 'airflow')
database = os.environ.get('DB_NAME', 'airflow')

print(f'Connecting to {host}:{port}...')

for i in range(30):
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=3
        )
        conn.close()
        print('Database connection successful!')
        sys.exit(0)
    except Exception as e:
        print(f'Attempt {i+1}/30: {e}')
        time.sleep(2)

print('Failed to connect to database after 30 attempts')
print('Check:')
print('  1. Is the database service running?')
print('  2. Is the hostname correct?')
print('  3. Are credentials correct?')
sys.exit(1)
"
}

# Основная логика
main() {
    # Проверяем обязательные переменные
    if [ -z "$AIRFLOW__DATABASE__SQL_ALCHEMY_CONN" ]; then
        echo "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN is not set"
        exit 1
    fi

    # Ждем базу данных
    wait_for_db

    # Инициализируем БД Airflow (если нужно)
    echo "Initializing Airflow database..."
    airflow db init

    # Создаем admin пользователя (если не существует)
    echo "Creating admin user..."
    airflow users create \
        --username admin \
        --firstname Admin \
        --lastname Admin \
        --role Admin \
        --email admin@example.com \
        --password admin 2>/dev/null || echo "Admin user already exists"

    # Создаем подключения (connections) для источников данных
    echo "Setting up connections..."

    # ClickHouse connection
    airflow connections add 'clickhouse_reports' \
        --conn-type 'clickhouse' \
        --conn-host 'clickhouse' \
        --conn-port '8123' \
        --conn-schema 'reports' \
        --conn-login 'default' \
        --conn-password '' 2>/dev/null || echo "ClickHouse connection already exists"

    # Эти можно добавить позже, когда будут созданы соответствующие сервисы
    # airflow connections add 'crm_postgres' ...
    # airflow connections add 'telemetry_postgres' ...

    echo "Airflow initialization complete"
    echo "Starting Airflow..."
    echo "========================================="

    # Запускаем вебсервер и шедулер
    airflow webserver & airflow scheduler
}

# Запускаем основную функцию
main