# BionicPRO Reports API

Бэкенд-сервис для выдачи отчётов по пользователям. Читает данные из OLAP-витрины (таблица `report_datamart`), подготовленной ETL (Apache Airflow). Вычислений в реальном времени не выполняет.

## Технологии

- Java 17, Spring Boot 3.2
- Spring Data JPA, PostgreSQL (OLAP)

## Ограничение доступа

Доступ к отчёту предоставляется **только в отношении себя**: пользователь может запрашивать только свой отчёт. Запросы к API требуют аутентификации по JWT (Bearer token, Keycloak).

- **GET /api/reports/me** — отчёт текущего пользователя (без указания userId).
- **GET /api/reports/user/{userId}** — отчёт по пользователю; разрешён только если `userId` совпадает с текущим пользователем (иначе 403).

Без токена или с невалидным токеном — 401. Запрос чужого userId — 403.

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/reports/me` | Отчёт текущего пользователя. Заголовок `Authorization: Bearer <JWT>`. 200 / 404. |
| GET | `/api/reports/user/{userId}` | Отчёт по пользователю; доступен только если userId = текущий пользователь. 200 / 401 / 403 / 404. |

Пример ответа:

```json
{
  "userId": "user-123",
  "deviceId": "device-456",
  "customerName": "Иван Иванов",
  "customerEmail": "ivan@example.com",
  "contractDate": "2024-01-15",
  "prosthesisModel": "BionicPRO v2",
  "deliveryDate": "2024-02-01",
  "sessionCount": 42,
  "totalUsageSeconds": 36000,
  "totalUsageMinutes": 600,
  "eventCount": 120,
  "errorCount": 2,
  "calibrationCount": 5,
  "periodStart": "2024-12-01T00:00:00Z",
  "periodEnd": "2024-12-31T23:59:59Z",
  "lastActivityUtc": "2024-12-30T14:22:00Z",
  "updatedAt": "2024-12-31T02:15:00Z"
}
```

## Конфигурация

Переменные окружения (или `application.yml`):

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `SERVER_PORT` | Порт HTTP | 8000 |
| `OLAP_DATASOURCE_URL` | JDBC URL OLAP БД | jdbc:postgresql://localhost:5434/olap_reports |
| `OLAP_DATASOURCE_USERNAME` | Пользователь OLAP | olap_user |
| `OLAP_DATASOURCE_PASSWORD` | Пароль OLAP | olap_password |
| `KEYCLOAK_ISSUER_URI` | URI realm Keycloak для проверки JWT | http://localhost:8080/realms/reports-realm |

Схема витрины и создание таблиц — в `Task2/airflow/sql/01_schema_olap.sql`. Данные в витрину заливает DAG Airflow `reports_etl`.

## Запуск

1. Поднять OLAP PostgreSQL и применить схему (см. Task2/airflow).
2. Запуск приложения:

```bash
cd backend
./mvnw spring-boot:run
```

Или сборка JAR:

```bash
./mvnw -q package
java -jar target/reports-api-1.0.0-SNAPSHOT.jar
```

Проверка: `GET http://localhost:8000/api/reports/user/<userId>`.
