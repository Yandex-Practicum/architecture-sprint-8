#!/bin/bash
# Скрипт инициализации ClickHouse
# Выполняется после запуска контейнера

set -e

echo "Ожидание запуска ClickHouse..."
sleep 10

# Проверка доступности ClickHouse
until clickhouse-client --query "SELECT 1" > /dev/null 2>&1; do
    echo "Ожидание ClickHouse..."
    sleep 2
done

echo "ClickHouse доступен, создание базы данных и схемы..."

# Создание базы данных
clickhouse-client --query "CREATE DATABASE IF NOT EXISTS bionicpro_reports"

# Выполнение SQL схемы
if [ -f /etc/clickhouse-server/clickhouse_schema.sql ]; then
    clickhouse-client --password="${CLICKHOUSE_PASSWORD:-clickhouse_password}" --database=bionicpro_reports < /etc/clickhouse-server/clickhouse_schema.sql
    echo "Схема ClickHouse создана успешно"
else
    echo "Предупреждение: файл clickhouse_schema.sql не найден"
fi

echo "Инициализация ClickHouse завершена"
