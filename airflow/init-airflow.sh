#!/bin/bash
# ============================================================================
# Airflow Initialization Script for BionicPRO ETL
# ============================================================================

set -e

echo "Waiting for Airflow webserver to be ready..."
sleep 30

echo "Creating Airflow connections..."

# CRM Database Connection (PostgreSQL)
airflow connections add 'bionicpro_crm_db' \
    --conn-type 'postgres' \
    --conn-host 'crm_db' \
    --conn-schema 'crm_db' \
    --conn-login 'crm_user' \
    --conn-password 'crm_password' \
    --conn-port '5432' \
    || echo "Connection bionicpro_crm_db already exists"

# Telemetry Database Connection (PostgreSQL)
airflow connections add 'bionicpro_telemetry_db' \
    --conn-type 'postgres' \
    --conn-host 'telemetry_db' \
    --conn-schema 'telemetry_db' \
    --conn-login 'telemetry_user' \
    --conn-password 'telemetry_password' \
    --conn-port '5432' \
    || echo "Connection bionicpro_telemetry_db already exists"

# ClickHouse Connection
airflow connections add 'bionicpro_clickhouse' \
    --conn-type 'generic' \
    --conn-host 'clickhouse' \
    --conn-login 'etl_user' \
    --conn-password 'etl_password_change_me' \
    --conn-port '9000' \
    || echo "Connection bionicpro_clickhouse already exists"

echo "Unpausing DAG bionicpro_reports_etl..."
airflow dags unpause bionicpro_reports_etl || echo "DAG not found yet, will be unpaused on first load"

echo "Airflow initialization complete!"
