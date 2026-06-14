#!/bin/bash
set -euo pipefail

bootstrap_src="/opt/ldap-bootstrap/bootstrap.ldif"
bootstrap_dest="/container/service/slapd/assets/config/bootstrap/ldif/custom/50-bootstrap.ldif"

if [ -d /var/lib/ldap ] && [ "$(ls -A /var/lib/ldap)" ]; then
  echo "*** INFO   | $(date '+%Y-%m-%d %H:%M:%S') | LDAP database already exists; skipping custom bootstrap ldif."
else
  echo "*** INFO   | $(date '+%Y-%m-%d %H:%M:%S') | Copying custom bootstrap ldif..."
  cp "$bootstrap_src" "$bootstrap_dest"
fi

exec /container/tool/run "$@"
