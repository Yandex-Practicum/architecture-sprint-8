#!/usr/bin/env bash
set -euo pipefail

KC="docker exec architecture-bionicpro-keycloak-1 /opt/keycloak/bin/kcadm.sh"
REALM=reports-realm
YANDEX_CLIENT_ID="${YANDEX_CLIENT_ID:-CHANGE_ME_YANDEX_CLIENT_ID}"
YANDEX_CLIENT_SECRET="${YANDEX_CLIENT_SECRET:-CHANGE_ME_YANDEX_CLIENT_SECRET}"

echo "== login =="
$KC config credentials --server http://localhost:8080 --realm master --user admin --password admin

echo "== access token lifespan <= 2 min =="
$KC update realms/$REALM -s accessTokenLifespan=120

echo "== PKCE + backend-driven redirect on reports-frontend =="
CID=$($KC get clients -r $REALM -q clientId=reports-frontend --fields id --format csv --noquotes | tail -1)
$KC update clients/$CID -r $REALM \
  -s 'redirectUris=["http://localhost:8081/login/oauth2/code/keycloak"]' \
  -s 'webOrigins=["http://localhost:8081"]' \
  -s directAccessGrantsEnabled=false \
  -s standardFlowEnabled=true \
  -s publicClient=true \
  -s consentRequired=true \
  -s 'attributes."pkce.code.challenge.method"=S256'

echo "== LDAP user federation (openldap, per-representative-office source) =="
REALM_ID=$($KC get realms/$REALM --fields id --format csv --noquotes | tail -1)
$KC create components -r $REALM \
  -s name=openldap-branch \
  -s providerId=ldap \
  -s providerType=org.keycloak.storage.UserStorageProvider \
  -s parentId=$REALM_ID \
  -s 'config.enabled=["true"]' \
  -s 'config.vendor=["other"]' \
  -s 'config.connectionUrl=["ldap://openldap:389"]' \
  -s 'config.usersDn=["ou=People,dc=example,dc=com"]' \
  -s 'config.bindDn=["cn=admin,dc=example,dc=com"]' \
  -s 'config.bindCredential=["admin"]' \
  -s 'config.usernameLDAPAttribute=["uid"]' \
  -s 'config.rdnLDAPAttribute=["uid"]' \
  -s 'config.uuidLDAPAttribute=["entryUUID"]' \
  -s 'config.userObjectClasses=["inetOrgPerson, organizationalPerson"]' \
  -s 'config.editMode=["READ_ONLY"]' \
  -s 'config.syncRegistrations=["false"]' \
  -s 'config.pagination=["true"]'

LDAP_ID=$($KC get components -r $REALM -q name=openldap-branch --fields id --format csv --noquotes | tail -1)

echo "== role mapper: LDAP groups (ou=Groups) -> realm roles =="
$KC create components -r $REALM \
  -s name=role-mapper \
  -s providerId=role-ldap-mapper \
  -s providerType=org.keycloak.storage.ldap.mappers.LDAPStorageMapper \
  -s parentId=$LDAP_ID \
  -s 'config."roles.dn"=["ou=Groups,dc=example,dc=com"]' \
  -s 'config."role.name.ldap.attribute"=["cn"]' \
  -s 'config."role.object.classes"=["groupOfNames"]' \
  -s 'config."membership.ldap.attribute"=["member"]' \
  -s 'config."membership.attribute.type"=["DN"]' \
  -s 'config."membership.user.ldap.attribute"=["uid"]' \
  -s 'config."mode"=["READ_ONLY"]' \
  -s 'config."use.realm.roles.mapping"=["true"]'

echo "== trigger a full LDAP sync so role mappings apply immediately (otherwise they"
echo "   only resolve lazily, the next time each user is loaded/logs in) =="
$KC create "user-storage/$LDAP_ID/sync?action=triggerFullSync" -r $REALM -o

echo "== mandatory OTP: forced setup on first login, then required every login =="
$KC update authentication/required-actions/CONFIGURE_TOTP -r $REALM -s enabled=true -s defaultAction=true

echo "== Yandex ID identity broker (generic OIDC provider pointed at Yandex OAuth endpoints) =="
$KC create identity-provider/instances -r $REALM \
  -s alias=yandex \
  -s providerId=oidc \
  -s enabled=true \
  -s storeToken=true \
  -s trustEmail=true \
  -s firstBrokerLoginFlowAlias="first broker login" \
  -s 'config.clientId='"$YANDEX_CLIENT_ID" \
  -s 'config.clientSecret='"$YANDEX_CLIENT_SECRET" \
  -s 'config.clientAuthMethod=client_secret_post' \
  -s 'config.authorizationUrl=https://oauth.yandex.ru/authorize' \
  -s 'config.tokenUrl=https://oauth.yandex.ru/token' \
  -s 'config.userInfoUrl=https://login.yandex.ru/info?format=json' \
  -s 'config.defaultScope=login:email login:info' \
  -s 'config.useJwksUrl=false' \
  -s 'config.syncMode=IMPORT'

echo "== import Yandex profile fields into Keycloak user attributes =="
$KC create identity-provider/instances/yandex/mappers -r $REALM \
  -s name=email -s identityProviderAlias=yandex -s identityProviderMapper=oidc-user-attribute-idp-mapper \
  -s 'config.claim=default_email' -s 'config."user.attribute"=email' -s 'config.syncMode=INHERIT'
$KC create identity-provider/instances/yandex/mappers -r $REALM \
  -s name=first-name -s identityProviderAlias=yandex -s identityProviderMapper=oidc-user-attribute-idp-mapper \
  -s 'config.claim=first_name' -s 'config."user.attribute"=firstName' -s 'config.syncMode=INHERIT'
$KC create identity-provider/instances/yandex/mappers -r $REALM \
  -s name=last-name -s identityProviderAlias=yandex -s identityProviderMapper=oidc-user-attribute-idp-mapper \
  -s 'config.claim=last_name' -s 'config."user.attribute"=lastName' -s 'config.syncMode=INHERIT'

echo "== export realm =="
CONTAINER=architecture-bionicpro-keycloak-1
docker exec "$CONTAINER" /opt/keycloak/bin/kc.sh export --dir /tmp/kc-export --realm $REALM --users skip
docker cp "$CONTAINER":/tmp/kc-export/$REALM-realm.json ./keycloak/keycloak-results-export.json
echo "wrote ./keycloak/keycloak-results-export.json"
