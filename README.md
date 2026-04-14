
# запуск: 

docker compose up

# вход в openldap

- username: cn=admin,dc=example,dc=com
- password: admin123

дополнительный вызов команды:
```
docker exec openldap ldapadd -x -H ldap://localhost:389 -D "cn=admin,dc=example,dc=com" -w admin123 -f /container/service/slapd/assets/config/bootstrap/ldif/custom/config.ldif
```


# Прописать hosts 
127.0.0.1       api.bio-pro.local
127.0.0.1       key.bio-pro.local
127.0.0.1       front.bio-pro.local


# export всех настроек KeyCloak
```
/opt/keycloak/bin/kc.sh export --dir /tmp/keycloak-export --users realm_file
```