#!/bin/sh
set -eu

template="/opt/keycloak/data/import-src/keycloak-results-export.json"
rendered="/opt/keycloak/data/import/keycloak-results-export.json"

: "${FRONTEND_BASE_URL:=https://localhost:3000}"
: "${AUTH_EXTERNAL_BASE_URL:=https://localhost:3000/api}"
: "${AUTH_CALLBACK_URL:=${AUTH_EXTERNAL_BASE_URL%/}/auth/callback}"
: "${POST_LOGOUT_REDIRECT_URIS:=${FRONTEND_BASE_URL%/}/*}"
: "${YANDEX_CLIENT_ID:=}"
: "${YANDEX_CLIENT_SECRET:=}"
: "${YANDEX_DEFAULT_SCOPE:=login:email login:info}"

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

frontend_base_url_escaped=$(escape_sed_replacement "$FRONTEND_BASE_URL")
auth_callback_url_escaped=$(escape_sed_replacement "$AUTH_CALLBACK_URL")
post_logout_redirect_uris_escaped=$(escape_sed_replacement "$POST_LOGOUT_REDIRECT_URIS")
yandex_client_id_escaped=$(escape_sed_replacement "$YANDEX_CLIENT_ID")
yandex_client_secret_escaped=$(escape_sed_replacement "$YANDEX_CLIENT_SECRET")
yandex_default_scope_escaped=$(escape_sed_replacement "$YANDEX_DEFAULT_SCOPE")

mkdir -p /opt/keycloak/data/import
cp "$template" "$rendered"

sed -i \
  -e "s/__FRONTEND_BASE_URL__/${frontend_base_url_escaped}/g" \
  -e "s/__AUTH_CALLBACK_URL__/${auth_callback_url_escaped}/g" \
  -e "s/__POST_LOGOUT_REDIRECT_URIS__/${post_logout_redirect_uris_escaped}/g" \
  -e "s/__YANDEX_CLIENT_ID__/${yandex_client_id_escaped}/g" \
  -e "s/__YANDEX_CLIENT_SECRET__/${yandex_client_secret_escaped}/g" \
  -e "s/__YANDEX_DEFAULT_SCOPE__/${yandex_default_scope_escaped}/g" \
  "$rendered"

exec /opt/keycloak/bin/kc.sh start-dev --import-realm
