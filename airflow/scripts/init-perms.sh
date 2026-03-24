#!/usr/bin/env bash
set -euo pipefail

echo "[init-perms] Ensuring Airflow folders exist and are writable"

mkdir -p /opt/airflow/logs /opt/airflow/dags /opt/airflow/plugins

# We need root for chown (this container runs as 0:0).
uid="${AIRFLOW_UID:-50000}"

for p in /opt/airflow/logs /opt/airflow/dags /opt/airflow/plugins; do
  if chown -R "${uid}:0" "$p" 2>/tmp/chown_err; then
    echo "[init-perms] chown OK: $p -> ${uid}:0"
  else
    echo "[init-perms] WARN: cannot chown $p (often happens with bind mounts / certain filesystems). Continuing."
    sed -e 's/^/[init-perms]   /' /tmp/chown_err || true
  fi
done

# Logs should be writable for demo regardless of FS quirks.
chmod -R a+rwX /opt/airflow/logs || true

echo "[init-perms] Done"
