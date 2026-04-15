# BionicPRO — учебный стенд (архитектура и безопасность)

Монорепозиторий проектной работы: единый `docker compose` поднимает SSO, отчётный API, Airflow, ClickHouse, MinIO, CDN, Kafka и Debezium. Ниже — навигация по спринтам и кратко, что в каждом из них сделано.

## Задачи (task1–task4)

| Спринт | Суть | Документация |
|--------|------|----------------|
| **Task 1** | Безопасный вход: PKCE, сессии через `bionicpro-auth`, Keycloak, MFA (TOTP), LDAP, брокер Яндекс ID | [README](task1/README.md) · [QUICKSTART](task1/QUICKSTART.md) · [отчёт](task1/TASK1_COMPLETION_REPORT.md) · [C4 drawio](task1/architecture-diagram.drawio) |
| **Task 2** | Отчёты: ETL из CRM в ClickHouse (Airflow), витрина, Reports API (JWT, RBAC по `buyer_id`), UI | [README](task2/README.md) · [QUICKSTART](task2/QUICKSTART.md) · [отчёт](task2/TASK2_COMPLETION_REPORT.md) · [диаграмма](task2/architecture-diagram.puml) |
| **Task 3** | Разгрузка OLAP: кеш отчётов в S3 (MinIO), раздача через Nginx (CDN), инвалидация при ETL | [README](task3/README.md) · [QUICKSTART](task3/QUICKSTART.md) · [отчёт](task3/TASK3_COMPLETION_REPORT.md) · [summary](task3/SUMMARY.md) |
| **Task 4** | CDC: изменения CRM → Debezium → Kafka → ClickHouse (`KafkaEngine` + materialized views), рядом с пакетным ETL | [README](task4/README.md) · [QUICKSTART](task4/QUICKSTART.md) · [отчёт](task4/TASK4_COMPLETION_REPORT.md) · [summary](task4/SUMMARY.md) |

Тексты формулировок заданий лежат в `taskN/task.txt`. Конспекты теории — в каталоге [`Theory/`](Theory/).

## Быстрый запуск

Нужны Docker и Docker Compose v2, ~8 GB RAM под Docker, свободные порты (в т.ч. 3000, 5000, 8000, 8080, 8081, 8083, 8123, 9000, 9093, 5433–5435, 6379, 389 и др. — см. compose и QUICKSTART задач).

```bash
cd /path/to/architecture-bionicpro
docker compose up -d --build
```

Дальше по сценарию:

- Airflow: http://127.0.0.1:8081 (`admin` / `admin`) — включить DAG `etl_crm_to_clickhouse`; при необходимости [airflow/setup-connections.sh](airflow/setup-connections.sh).
- Task 4: после старта проверить Kafka Connect и при необходимости [debezium/register-connector.sh](debezium/register-connector.sh) — детали в [task4/QUICKSTART.md](task4/QUICKSTART.md).

Остановка с данными: `docker compose down`; полная очистка томов: `docker compose down -v`.

## Сервисы в корне репозитория

| Каталог / файл | Назначение |
|----------------|------------|
| [docker-compose.yaml](docker-compose.yaml) | Все контейнеры |
| [bionicpro-auth/](bionicpro-auth/) | Flask: PKCE, сессии, выдача access token для API |
| [frontend/](frontend/) | React, вход через auth-сервис, отчёты |
| [reports-api/](reports-api/) | FastAPI + ClickHouse (+ S3/MinIO в task 3) |
| [airflow/](airflow/) | DAG ETL, init SQL для CRM и Debezium |
| [clickhouse/](clickhouse/) | Init схемы OLAP и (task 4) Kafka CDC |
| [debezium/](debezium/) | JSON коннектора и скрипт регистрации |
| [keycloak/](keycloak/) | Realm, инструкции MFA |
| [ldap/](ldap/) | OpenLDAP bootstrap и инструкция |
| [cdn/](cdn/) | Nginx для CDN (task 3) |

## Дополнительная настройка (Keycloak / LDAP / Яндекс)

- LDAP: [ldap/LDAP_SETUP_INSTRUCTIONS.md](ldap/LDAP_SETUP_INSTRUCTIONS.md)
- MFA: [keycloak/MFA_OTP_SETUP_INSTRUCTIONS.md](keycloak/MFA_OTP_SETUP_INSTRUCTIONS.md)
- Яндекс ID: [YANDEX_ID_SETUP.md](YANDEX_ID_SETUP.md)
- Экспорт realm: [KEYCLOAK_EXPORT_INSTRUCTIONS.md](KEYCLOAK_EXPORT_INSTRUCTIONS.md)

## Тестовые пользователи (Keycloak)

Локальные: `prothetic1` / `prothetic123`, `prothetic2` / `prothetic123`, `admin1` / `admin123`. После настройки LDAP — см. [task1/README.md](task1/README.md). При первом входе у пользователей с включённым TOTP нужно настроить OTP в приложении-аутентификаторе.

## Полезные эндпоинты

- Frontend: http://127.0.0.1:3000  
- Auth: http://127.0.0.1:5000/health  
- Reports API: http://127.0.0.1:8000/docs  
- Keycloak: http://127.0.0.1:8080  

Подробные списки API и портов — в README соответствующих task.

## Отладка

```bash
docker compose logs keycloak
docker compose logs bionicpro-auth
docker compose logs reports-api
docker compose logs kafka-connect   # task 4
```
