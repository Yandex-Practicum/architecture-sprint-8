#!/bin/bash

# Script to fix common startup issues with BionicPro architecture

echo "=== BionicPro Startup Issues Fixer ==="
echo

# Function to check if a container is running
is_container_running() {
    docker ps --format "{{.Names}}" | grep -q "^$1$"
    return $?
}

# Function to check container exit code
check_container_status() {
    local container_name=$1
    local status=$(docker ps -a --filter "name=^${container_name}$" --format "{{.Status}}")

    if echo "$status" | grep -q "Exited"; then
        local exit_code=$(echo "$status" | grep -oP 'Exited \(\K[0-9]+')
        echo "$exit_code"
    else
        echo "running"
    fi
}

echo "Checking for common issues..."
echo

# Check ClickHouse
clickhouse_status=$(check_container_status "bionicpro-clickhouse")
if [[ "$clickhouse_status" == "70" ]] || [[ "$clickhouse_status" == "1" ]]; then
    echo "⚠️  ClickHouse has crashed (Exit code: $clickhouse_status)"
    echo "   Fixing ClickHouse..."

    # Stop and remove ClickHouse container
    docker stop bionicpro-clickhouse 2>/dev/null
    docker rm bionicpro-clickhouse 2>/dev/null

    # Remove and recreate ClickHouse data volume
    docker volume rm architecture-bionicpro_clickhouse-data 2>/dev/null
    echo "   ✓ ClickHouse data volume cleaned"

    # Restart ClickHouse
    docker-compose up -d clickhouse
    echo "   ✓ ClickHouse restarted"
    echo
elif [[ "$clickhouse_status" == "running" ]]; then
    echo "✓ ClickHouse is running normally"
    echo
else
    echo "⚠️  ClickHouse is not running"
    echo
fi

# Check OpenLDAP
openldap_status=$(check_container_status "bionicpro-openldap")
if [[ "$openldap_status" == "1" ]]; then
    echo "⚠️  OpenLDAP has crashed (Exit code: 1)"
    echo "   Fixing OpenLDAP..."

    # Stop and remove OpenLDAP container
    docker stop bionicpro-openldap 2>/dev/null
    docker rm bionicpro-openldap 2>/dev/null

    # Remove OpenLDAP volumes to ensure clean state
    docker volume rm architecture-bionicpro_ldap-data 2>/dev/null
    docker volume rm architecture-bionicpro_ldap-config 2>/dev/null
    echo "   ✓ OpenLDAP volumes cleaned"

    # Restart OpenLDAP
    docker-compose up -d openldap
    echo "   ✓ OpenLDAP restarted"
    echo
elif [[ "$openldap_status" == "running" ]]; then
    echo "✓ OpenLDAP is running normally"
    echo
else
    echo "⚠️  OpenLDAP is not running"
    echo
fi

# Wait for services to stabilize
echo "Waiting for services to stabilize..."
sleep 10

# Check final status
echo
echo "=== Final Status ==="
clickhouse_final=$(check_container_status "bionicpro-clickhouse")
openldap_final=$(check_container_status "bionicpro-openldap")

if [[ "$clickhouse_final" == "running" ]]; then
    echo "✓ ClickHouse: Running"
else
    echo "✗ ClickHouse: Not running (Status: $clickhouse_final)"
fi

if [[ "$openldap_final" == "running" ]]; then
    echo "✓ OpenLDAP: Running"
else
    echo "✗ OpenLDAP: Not running (Status: $openldap_final)"
fi

echo
echo "=== Fix completed ==="
echo
echo "If services are still failing, check logs with:"
echo "  docker-compose logs clickhouse"
echo "  docker-compose logs openldap"
