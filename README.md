## Настройка Keycloak

Для подключения к master realm без HTTPS необходимо выполнить следующие команды внутри контейнера
Keycloak:

```bash
./kcadm.sh config credentials --server http://localhost:8080 --realm master --user admin --password admin
./kcadm.sh update realms/master -s sslRequired=NONE
```

Эти команды отключают требование SSL для master realm, что позволяет подключаться по HTTP.
