#!/bin/bash
# Wait for Keycloak to start
echo "Waiting for Keycloak to start..."
sleep 30

# Configure kcadm - use keycloak service name instead of localhost
/opt/keycloak/bin/kcadm.sh config credentials \
  --server http://keycloak:8080 \
  --realm master \
  --user admin \
  --password admin

# Disable SSL requirement for master realm
echo "Configuring SSL settings for master realm..."
/opt/keycloak/bin/kcadm.sh update realms/master -s sslRequired=NONE

echo "Master realm configuration completed!"
