#!/bin/bash
# Скрипт для настройки подключений в Airflow

echo "Настройка подключений Airflow..."

# CRM PostgreSQL Connection
docker exec bionicpro-airflow-webserver airflow connections add 'crm_postgres' \
    --conn-type 'postgres' \
    --conn-host 'crm_db' \
    --conn-schema 'crm_db' \
    --conn-login 'crm_user' \
    --conn-password 'crm_password' \
    --conn-port 5432

echo "✅ Подключение crm_postgres создано"

# ClickHouse Connection (если потребуется)
docker exec bionicpro-airflow-webserver airflow connections add 'clickhouse_default' \
    --conn-type 'http' \
    --conn-host 'clickhouse' \
    --conn-port 8123

echo "✅ Подключение clickhouse_default создано"

echo "Все подключения настроены!"
