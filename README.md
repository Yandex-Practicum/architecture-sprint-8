
```bash
docker-compose up -d --build
```
Зайти на `https://localhost:3000`

См. отчёт

Airflow: `http://localhost:8083`. `admin`:`admin`


## Обзор системы

Система BionicPRO была переработана для повышения безопасности и включает в себя:

1. **OAuth 2.0 с PKCE** - защищенная аутентификация
2. **LDAP интеграция** - для международных представительств
3. **MFA (TOTP)** - двухфакторная аутентификация
4. **Яндекс ID** - внешний провайдер аутентификации
5. **Сервис отчетов** - с кешированием в S3 и CDN
6. **CDC с Debezium** - для реального времени данных
7. **Предзагруженные отчеты** - тестовые данные для трех CRM пользователей

## Доступные сервисы

| Сервис | URL | Описание |
|--------|-----|----------|
| Frontend | http://localhost:3000 | React приложение |
| BionicPRO Auth | http://localhost:5001 | сервис аутентификации |
| Reports API | http://localhost:5003 |  сервис отчетов |
| Keycloak | http://localhost:8080 | Identity Provider |
| Airflow UI | http://localhost:8083 | ETL процессы |
| ClickHouse | http://localhost:8123 | OLAP база данных |
| MinIO | http://localhost:9001 | S3 совместимое хранилище |
| Nginx CDN | http://localhost:8888 | CDN для отчетов |
| Kafka UI | http://localhost:8082 | Kafka управление |
| Debezium | http://localhost:8084 | CDC коннектор |
