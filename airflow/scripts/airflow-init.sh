#!/usr/bin/env bash
set -euo pipefail

echo "[airflow-init] Checking database state"
if airflow db check; then
  echo "[airflow-init] Metadata database already initialized"
else
  echo "[airflow-init] Initializing metadata database (airflow db init)"
  airflow db init
fi

echo "[airflow-init] Running DB migrations to ensure schema is up to date"
airflow db migrate
echo "[airflow-init] Database migration done!"

# Create the first user account (idempotent).
USERNAME="${_AIRFLOW_WWW_USER_USERNAME:-admin}"
PASSWORD="${_AIRFLOW_WWW_USER_PASSWORD:-admin}"
FIRSTNAME="${_AIRFLOW_WWW_USER_FIRSTNAME:-Air}"
LASTNAME="${_AIRFLOW_WWW_USER_LASTNAME:-Flow}"
ROLE="${_AIRFLOW_WWW_USER_ROLE:-Admin}"
EMAIL="${_AIRFLOW_WWW_USER_EMAIL:-admin@example.com}"

python - <<'PY'
import os, re, subprocess, sys

u = os.environ.get("USERNAME", "admin")
p = subprocess.run(["airflow","users","list"], capture_output=True, text=True)
if p.returncode != 0:
    print(p.stdout)
    print(p.stderr, file=sys.stderr)
    sys.exit(p.returncode)

# The CLI prints a table; checking for the username as a separate token is sufficient for demo.
if re.search(rf"\b{re.escape(u)}\b", p.stdout):
    print(f"[airflow-init] User '{u}' already exists; skipping create.")
    sys.exit(0)

sys.exit(1)
PY
# If python exits 0 -> exists, 1 -> not found (create), other -> error.
RC=$?
if [ "$RC" -eq 0 ]; then
  exit 0
elif [ "$RC" -ne 1 ]; then
  echo "[airflow-init] ERROR: failed to check existing users"
  exit "$RC"
fi

echo "[airflow-init] Creating user: ${USERNAME}"
airflow users create \
  --username "${USERNAME}" \
  --password "${PASSWORD}" \
  --firstname "${FIRSTNAME}" \
  --lastname "${LASTNAME}" \
  --role "${ROLE}" \
  --email "${EMAIL}"

echo "[airflow-init] Done"
