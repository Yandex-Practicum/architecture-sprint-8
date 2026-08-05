#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

curl -i -X POST -H "Content-Type: application/json" \
  --data @"$DIR/crm-connector.json" \
  http://localhost:8083/connectors
