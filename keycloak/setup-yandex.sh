#!/usr/bin/env bash
# Подставляет креды Яндекс ID в Identity Provider realm reports-realm.
# Важно: креды берутся из окружения или .env и в репозиторий не попадают.
# Использование:
#   export YANDEX_CLIENT_ID=... YANDEX_CLIENT_SECRET=...   (или заполнить .env)
#   ./keycloak/setup-yandex.sh [keycloak_url]              (по умолчанию :8080)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$DIR/.env" ] && set -a && . "$DIR/.env" && set +a

KC_URL="${1:-http://localhost:8080}"
: "${YANDEX_CLIENT_ID:?нужна переменная YANDEX_CLIENT_ID}"
: "${YANDEX_CLIENT_SECRET:?нужна переменная YANDEX_CLIENT_SECRET}"

TOKEN=$(curl -sf -X POST "$KC_URL/realms/master/protocol/openid-connect/token" \
  -d grant_type=password -d client_id=admin-cli \
  -d username=admin -d password=admin \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -sf "$KC_URL/admin/realms/reports-realm/identity-provider/instances/yandex" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "
import sys, json, os
d = json.load(sys.stdin)
d['config']['clientId'] = os.environ['YANDEX_CLIENT_ID']
d['config']['clientSecret'] = os.environ['YANDEX_CLIENT_SECRET']
json.dump(d, open('/tmp/yandex-idp.json', 'w'))
"

curl -sf -X PUT "$KC_URL/admin/realms/reports-realm/identity-provider/instances/yandex" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  --data @/tmp/yandex-idp.json \
  && echo "OK: Яндекс ID настроен из переменных окружения"
