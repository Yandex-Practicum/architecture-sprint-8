#!/usr/bin/env bash
# Генерирует самоподписанный TLS-сертификат для локального HTTPS-листенера
# Keycloak (порт 8443). Последние версии Keycloak всегда помечают cookie
# сессии аутентификации как Secure; SameSite=None, поэтому браузерному
# эндпоинту нужен настоящий (пусть и самоподписанный) TLS-листенер, чтобы
# вход работал через localhost. Запустите один раз перед `docker compose up`.
set -euo pipefail
cd "$(dirname "$0")"

openssl req -x509 -newkey rsa:2048 -keyout server.key.pem -out server.crt.pem \
  -days 3650 -nodes -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "Generated keycloak/certs/server.crt.pem and server.key.pem"
