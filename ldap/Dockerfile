# LDIF внутри образа: bind-mount на .../bootstrap/ldif/custom ломает rm при старте osixia/openldap.
FROM osixia/openldap:1.5.0
COPY custom/50-bionic.ldif /container/service/slapd/assets/config/bootstrap/ldif/custom/50-bionic.ldif
