
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


# Настройка DAG

## Инициалиация airflow
docker compose exec airflow-webserver airflow users create \
    --username admin \
    --password admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com

## Добавление подключения к остальным БД
```
docker compose exec airflow-webserver airflow connections add 'crm_connection' \
    --conn-type 'postgres' \
    --conn-host 'postgres_crm' \
    --conn-login 'crm_user' \
    --conn-password 'crm_password' \
    --conn-schema 'crm_db' \
    --conn-port '5432'


docker compose exec airflow-webserver airflow connections add 'telemetry_connection' \
    --conn-type 'postgres' \
    --conn-host 'postgres_telemetry' \
    --conn-login 'telemetry_user' \
    --conn-password 'telemetry_password' \
    --conn-schema 'telemetry_db' \
    --conn-port '5432'


docker compose exec airflow-webserver airflow connections add 'clickhouse_connection' \
    --conn-type 'http' \
    --conn-host 'clickhouse' \
    --conn-port '8123' \
    --conn-schema 'default'
```
