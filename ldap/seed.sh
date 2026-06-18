#!/bin/sh
set -e

LDIF="/seed.ldif"
echo "[seed] waiting for openldap..."
for i in $(seq 1 60); do
  if ldapsearch -x -H ldap://openldap:389 -b "" -s base "+" >/dev/null 2>&1; then
    echo "[seed] openldap is up."
    break
  fi
  sleep 2
done

if ! ldapsearch -x -H ldap://openldap:389 -b "dc=bionicpro,dc=com" "(objectclass=inetOrgPerson)" uid >/dev/null 2>&1; then
  echo "[seed] loading LDIF..."
  ldapadd -x -H ldap://openldap:389 \
    -D "cn=admin,dc=bionicpro,dc=com" \
    -w "ldap_admin_password" \
    -f "$LDIF" -c
  echo "[seed] done."
else
  echo "[seed] users already present, skipping."
fi