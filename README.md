
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

https://auth.yandex.cloud/error?problem=%7B%22title%22%3A%22invalid_client%22%2C%22status%22%3A401%2C%22detail%22%3A%22No%20client%20with%20requested%20id%3A%20698b0d312530487d96709f431e8161cc%22%2C%22instance%22%3A%22%2Foauth%2Fauthorize%22%2C%22request-id%22%3A%22b56f2810-d158-4720-a13a-610ed67d2593%22%7D