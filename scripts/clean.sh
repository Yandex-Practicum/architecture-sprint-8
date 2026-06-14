#!/bin/bash
# Clean all persistent data for fresh start
# Usage: ./scripts/clean.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Stopping containers..."
docker compose down -v 2>/dev/null || true

echo "Removing data directories..."
DATA_DIRS=(
    "clickhouse-data"
    "ldap-config"
    "ldap-data"
    "minio-data"
    "postgres-airflow-data"
    "postgres-bionicpro-data"
    "postgres-crm-data"
    "postgres-keycloak-data"
    "postgres-telemetry-data"
    "redis-data"
)

for dir in "${DATA_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "  Removing $dir/"
        rm -rf "$dir"
    fi
done

echo "Done! Run 'docker compose up -d' for a fresh start."
