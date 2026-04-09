# Проверка работоспособности системы BionicPro

## Запуск системы с нуля

```bash
# 1. Остановить и удалить все контейнеры и volumes (чистый запуск)
docker-compose down -v

# 2. Запустить всю систему
docker-compose up -d

# 3. Подождать 30-60 секунд для полной инициализации всех сервисов
```

## Проверка статуса контейнеров

```bash
# Проверить статус всех контейнеров
docker ps -a

# Все контейнеры должны быть в статусе "Up" кроме:
# - bionicpro-airflow-init (Exited 0 - это нормально, инициализация завершена)
# - bionicpro-minio-init (Exited 0 - это нормально, инициализация завершена)
# - bionicpro-debezium-register (может быть Exited 0 после регистрации коннектора)
```

## Критические проверки после исправлений

### 1. ClickHouse (исправлена проблема с Exit code 70)
```bash
# Проверить статус
docker ps | grep clickhouse
# Должен показать: bionicpro-clickhouse ... Up ...

# Проверить логи
docker logs bionicpro-clickhouse --tail 20
# НЕ должно быть ошибок, последние строки должны содержать "Ready for connections"

# Проверить доступность web-интерфейса
curl -s http://localhost:8123/ | head -n 1
# Должно вернуть: Ok.
```

### 2. OpenLDAP (исправлен конфликт доменов dc=example → dc=bionicpro)
```bash
# Проверить статус
docker ps | grep openldap
# Должен показать: bionicpro-openldap ... Up ...

# Проверить логи
docker logs bionicpro-openldap --tail 10
# НЕ должно быть ошибок о несовпадении доменов

# Проверить LDAP структуру
docker exec bionicpro-openldap ldapsearch -x -b "dc=bionicpro,dc=com" -D "cn=admin,dc=bionicpro,dc=com" -w admin123 "(objectClass=*)" dn 2>/dev/null | grep "dn:"
# Должно показать список DN с dc=bionicpro,dc=com
```

### 3. Keycloak (исправлен порт 8080 → 8088)
```bash
# Проверить доступность на правильном порту
curl -s http://localhost:8088/health | grep -o '"status":"UP"'
# Должно вернуть: "status":"UP"

# Проверить admin консоль
curl -s -o /dev/null -w "%{http_code}" http://localhost:8088/admin/
# Должно вернуть: 200
```

## Проверка интеграций

### 4. Kafka и Debezium Connect
```bash
# Проверить Kafka
docker logs bionicpro-kafka --tail 5 | grep "started"

# Проверить Kafka Connect
curl -s http://localhost:8083/ | jq .version
# Должна показать версию Debezium

# Проверить зарегистрированные коннекторы
curl -s http://localhost:8083/connectors
# Должен показать ["crm-postgres-connector"] или пустой массив []
```

### 5. Airflow
```bash
# Проверить Airflow webserver
curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/health
# Должно вернуть: 200
```

### 6. MinIO
```bash
# Проверить MinIO API
curl -s -o /dev/null -w "%{http_code}" http://localhost:9002/minio/health/live
# Должно вернуть: 200

# Проверить MinIO Console
curl -s -o /dev/null -w "%{http_code}" http://localhost:9001/
# Должно вернуть: 200
```

### 7. Reports API
```bash
# Проверить API
curl -s http://localhost:8000/health
# Должно вернуть JSON со статусом
```

### 8. Frontend
```bash
# Проверить фронтенд
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/
# Должно вернуть: 200
```

## Итоговая проверка

Выполните команду для быстрой проверки всех критических сервисов:

```bash
echo "=== Проверка статуса сервисов BionicPro ==="
echo
echo "ClickHouse: $(docker ps --format "table {{.Names}}\t{{.Status}}" | grep clickhouse | awk '{print $2}')"
echo "OpenLDAP: $(docker ps --format "table {{.Names}}\t{{.Status}}" | grep openldap | awk '{print $2}')"
echo "Keycloak (port 8088): $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8088/health)"
echo "Kafka: $(docker ps --format "table {{.Names}}\t{{.Status}}" | grep kafka | grep -v connect | grep -v zookeeper | awk '{print $2}')"
echo "Airflow: $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/health)"
echo "Frontend: $(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/)"
echo "Reports API: $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)"
```

Все сервисы должны показывать статус "Up" или код ответа 200.

## Что было исправлено

1. **docker-compose.yaml**: Порт Keycloak изменен с 8080 на 8088
2. **ldap/config.ldif**: Все домены изменены с dc=example,dc=com на dc=bionicpro,dc=com
3. Эти изменения устраняют конфликты при запуске с нуля
