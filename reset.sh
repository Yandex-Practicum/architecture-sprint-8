#!/bin/bash
# Полный сброс: удаляет контейнеры, volumes, данные
# Использовать после неудачного запуска или для начала с чистого листа

set -e
echo "Stopping and removing containers..."
docker compose down -v --remove-orphans 2>/dev/null || true

echo "Removing persistent data directories..."
rm -rf postgres-keycloak-data postgres-crm-data postgres-airflow-data clickhouse-data

echo "Done! Ready for fresh start: docker compose up -d"
