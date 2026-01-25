# BionicPRO - Система отчётов о работе протезов

## Описание проекта

BionicPRO — это система для сбора, обработки и предоставления отчётов о работе бионических протезов. Система позволяет пользователям получать детальную аналитику о работе своих протезов за выбранные периоды времени.

## Основные компоненты

- **Backend API** (FastAPI) — REST API для получения отчётов с авторизацией через Keycloak
- **Frontend** (React + TypeScript) — веб-интерфейс для просмотра отчётов
- **Apache Airflow** — оркестрация ETL-процессов для обработки данных
- **ClickHouse** — OLAP хранилище для витрины отчётности
- **PostgreSQL** — хранение данных с датчиков протезов
- **Keycloak** — сервис аутентификации и авторизации

## Быстрый старт

```sh
docker compose -f docker-compose.yaml up -d --build
```

После запуска доступны:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Keycloak: http://localhost:8080
- Airflow: http://localhost:8081
