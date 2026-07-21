#!/bin/bash
set -e

echo "waiting for clickhouse..."
for _ in $(seq 1 60); do
  if clickhouse-client -h clickhouse --user bionic --password bionic -q 'SELECT 1' >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# Give Debezium a moment to create the topics and stream the initial snapshot.
echo "waiting for debezium topics/snapshot..."
sleep 20

echo "creating ClickHouse CDC objects..."
clickhouse-client -h clickhouse --user bionic --password bionic --multiquery < /config/01_cdc.sql
echo "CDC ClickHouse objects created"
