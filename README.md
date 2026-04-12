
# запуск: 

docker compose up

# вход в openldap

- username: cn=admin,dc=example,dc=com
- password: admin123

дополнительный вызов команды:
```
docker exec openldap ldapadd -x -H ldap://localhost:389 -D "cn=admin,dc=example,dc=com" -w admin123 -f /container/service/slapd/assets/config/bootstrap/ldif/custom/config.ldif
```