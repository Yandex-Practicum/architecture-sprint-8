#!/bin/bash
# Wait for Keycloak to start and import realm
echo "Waiting for Keycloak to start and import realms..."
sleep 40

# Configure kcadm - use keycloak service name instead of localhost
echo "Authenticating with Keycloak Admin API..."
/opt/keycloak/bin/kcadm.sh config credentials \
  --server http://keycloak:8080 \
  --realm master \
  --user admin \
  --password admin

# Check if reports-realm exists
echo "Checking if reports-realm exists..."
REALM_EXISTS=$(/opt/keycloak/bin/kcadm.sh get realms/reports-realm 2>/dev/null)
if [ -z "$REALM_EXISTS" ]; then
  echo "ERROR: reports-realm not found. Make sure realm-export.json is imported correctly."
  exit 1
fi

# Check if Yandex Identity Provider exists
echo "Checking if Yandex Identity Provider exists..."
IDP_EXISTS=$(/opt/keycloak/bin/kcadm.sh get identity-provider/instances/yandex -r reports-realm 2>/dev/null)
if [ -z "$IDP_EXISTS" ]; then
  echo "ERROR: Yandex Identity Provider not found in reports-realm."
  exit 1
fi

# Configure Yandex ID Identity Provider User Profile Claims
# Note: Keycloak has two sets of parameters:
# - *Attribute: for parsing UserInfo endpoint JSON response
# - *Claim: for UI "User profile claims" section
echo "Configuring Yandex ID User Profile Claims..."
# Note: Keycloak uses 'userIDClaim' (with capital D) and 'fullNameClaim' (not 'nameClaim')
/opt/keycloak/bin/kcadm.sh update identity-provider/instances/yandex -r reports-realm \
  -s 'config.userIdAttribute=id' \
  -s 'config.userNameAttribute=login' \
  -s 'config.emailAttribute=default_email' \
  -s 'config.nameAttribute=name' \
  -s 'config.givenNameAttribute=first_name' \
  -s 'config.familyNameAttribute=last_name' \
  -s 'config.userIDClaim=id' \
  -s 'config.userNameClaim=login' \
  -s 'config.emailClaim=default_email' \
  -s 'config.fullNameClaim=name' \
  -s 'config.givenNameClaim=first_name' \
  -s 'config.familyNameClaim=last_name'

if [ $? -eq 0 ]; then
  echo "✓ Yandex ID User Profile Claims configured successfully!"
  echo "  - ID Claim (userIDClaim): id"
  echo "  - Username Claim: login"
  echo "  - Email Claim: default_email"
  echo "  - Full Name Claim (fullNameClaim): name"
  echo "  - Given name Claim: first_name"
  echo "  - Family name Claim: last_name"
else
  echo "ERROR: Failed to configure Yandex ID User Profile Claims"
  exit 1
fi

echo "Yandex ID configuration completed!"
