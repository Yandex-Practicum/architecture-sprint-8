#!/bin/bash
# Полный сброс и перезапуск: основной проект + Airflow
set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Остановка основного проекта ==="
docker compose down -v 2>/dev/null || true

echo "=== Остановка Airflow ==="
cd airflow && docker compose down -v 2>/dev/null || true
cd "$PROJECT_ROOT"

echo "=== Удаление volumes и данных ==="
rm -rf postgres-keycloak-data crm-data olap-data clickhouse-data minio-data redis-data bionicpro-auth-data airflow/db 2>/dev/null || true
mkdir -p airflow/db
cp airflow/dags/sql/init-db.sql airflow/db/ 2>/dev/null || echo "CREATE DATABASE sample;" > airflow/db/init-db.sql
mkdir -p airflow/db

echo "=== .env ==="
echo "CLICKHOUSE_PASSWORD=clickhouse" > .env 2>/dev/null || true

echo "=== Запуск основного проекта ==="
docker compose up -d

echo "=== Ожидание готовности (2-3 мин)... ==="
sleep 120

echo "=== Сборка reports-etl ==="
docker build -t reports-etl:latest ./reports-etl 2>/dev/null || true

echo "=== Запуск Airflow ==="
cd airflow && docker compose up -d
cd "$PROJECT_ROOT"

echo ""
echo "Готово. Отчёт доступен после входа (user1 / password123):"
echo "  Frontend: http://localhost:3000"
echo "  Airflow:  http://localhost:8081 (admin / admin)"
