# BionicPro

## Запуск

```bash
docker compose up --build
```

Для запуска в фоне:

```bash
docker compose up --build -d
```

Остановка:

```bash
docker compose down
```

Остановка с удалением volumes:

```bash
docker compose down -v
```

## Порядок запуска

Docker Compose автоматически соблюдает порядок через `depends_on` и healthcheck-и:

1. `keycloak_db`, `airflow_db`, `clickhouse` — базы данных
2. `airflow-init` — миграции и создание admin-пользователя Airflow
3. `keycloak` — ждёт `keycloak_db`
4. `airflow-webserver`, `airflow-scheduler` — стартуют после успешного healthcheck `airflow-init` и `clickhouse`
5. `report_api` — стартует после `clickhouse` (healthy) и `keycloak`
6. `frontend` — стартует после `keycloak` и `report_api`

## Сервисы

| Сервис            | URL                   | Описание                        |
|-------------------|-----------------------|---------------------------------|
| Frontend          | http://localhost:3000 | React-приложение                |
| Report API        | http://localhost:8000 | Backend REST API                |
| Airflow Webserver | http://localhost:8081 | Airflow UI                      |
| Keycloak          | http://localhost:8080 | Identity Provider (OIDC/OAuth2) |

## Учётные данные

| Сервис   | Логин   | Пароль  |
|----------|---------|---------|
| Airflow  | `admin` | `admin` |
| Keycloak | `admin` | `admin` |
