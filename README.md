# Prosthetics Reporting System

## Обзор

Проект реализует систему сбора, обработки и предоставления отчётов по данным с протезов пациентов. Данные собираются из CRM и телеметрии устройств, загружаются в ClickHouse через ETL-пайплайн на Apache Airflow и предоставляются конечным пользователям (клиентам) через защищённый API и веб-интерфейс.

---

## Архитектура

### Диаграмма архитектуры (Задание 1)

Архитектурная диаграмма проекта представлена в файле:

```
bionic-pro-c4-new-concept_Task1.drawio
```

На диаграмме есть Легенда и необходимые пояснения к изменениям относительно текущей архитектуры.

### Реализация PKCE (Proof Key for Code Exchange)

PKCE реализован на всех уровнях: фронтенд → Keycloak → бэкенд (через Keycloak Client Policy).

#### На стороне Keycloak

В `keycloak/realm-export.json` настроен клиент `reports-frontend` с параметрами:

```json
"clients": [
  {
    "clientId": "reports-frontend",
    "publicClient": true,
    "standardFlowEnabled": true,
    "implicitFlowEnabled": false,
    "directAccessGrantsEnabled": false,
    "attributes": {
      "pkce.code.challenge.method": "S256"
    }
  }
]
```

**Ключевые настройки:**

- `"publicClient": true` — означает, что клиент не хранит секрет (подходит для SPA)
- `"pkce.code.challenge.method": "S256"` — требует использование SHA-256 для генерации code challenge
- Отключены небезопасные потоки (implicitFlow, directAccessGrants)

Это гарантирует, что Keycloak будет требовать PKCE при авторизации.

#### На фронтенде (React)

Фронтенд использует библиотеку `keycloak-js`, которая автоматически поддерживает PKCE, если клиент настроен как public.

Пример инициализации в коде (в `frontend/src/keycloak.js` или аналогичном):

```javascript
const keycloak = new Keycloak({
  url: 'http://localhost:8081',
  realm: 'reports-realm',
  clientId: 'reports-frontend'
});

keycloak.init({ 
  onLoad: 'login-required',
  pkceMethod: 'S256' // явно указываем метод
}).then(authenticated => {
  console.log("Authenticated:", authenticated);
});
```

При вызове `.init()` с `pkceMethod: 'S256'` библиотека:

1. Генерирует `code_verifier` (рандомная строка)
2. Вычисляет `code_challenge = base64url(sha256(code_verifier))`
3. Отправляет `code_challenge` при запросе авторизации
4. Передаёт `code_verifier` при обмене authorization_code на access_token

Таким образом, даже если authorization_code перехватят — без code_verifier его нельзя использовать.

#### На бэкенде (FastAPI)

Бэкенд не участвует в PKCE напрямую, так как это клиентская защита. Однако он валидирует токен, выданный Keycloak:

```python
def verify_access_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

> ⚠️ **Внимание:** В продакшене нужно проверять подпись токена через public key Keycloak.

Также есть дополнительная проверка доступа:

```python
def verify_client_access(request: Request, client_id: str):
    payload = verify_access_token(request)
    username = payload.get("preferred_username")
    if username != client_id:
        raise HTTPException(status_code=403, detail="Access denied")
```

Это обеспечивает привязку токена к запрашиваемому ресурсу (client_id), предотвращая доступ одного клиента к данным другого.

### Расширенная архитектура (Задание 2)

Диаграмма расширенной архитектуры находится в файле:

```
bionic-pro-c4-new-concept_Task2.drawio
```

Диаграмма сделана на базе первой и показывает изменения для реализации системы репортинга.


### Структура проекта

```
.
├── docker-compose.yaml            # Все сервисы
├── keycloak/                      # Realm export
├── frontend/                      # React UI
├── reports-backend/               # FastAPI сервер
├── dags/                          # Airflow DAG
├── init-scripts/                  # Инициализация БД
├── config/                        # Airflow connections
└── generate_dummy_data.py         # Генерация тестовых данных

```


---

## Как запустить проект

### Шаг 1: Запуск Docker-сервисов

```bash
docker-compose up --build
```

Убедитесь, что все контейнеры запустились:

- **Keycloak:** http://localhost:8081
- **Frontend:** http://localhost:3001
- **Airflow:** http://localhost:8082
- **ClickHouse:** http://localhost:8123
- **Reports Backend:** http://localhost:8000

Проверьте логи:

```bash
docker-compose logs -f
```

### Шаг 2: Генерация фейковых данных

Откройте новый терминал и запустите:

```bash
python generate_dummy_data.py
```

Скрипт добавит:

- 5 новых клиентов в `crm_db`
- Устройства для активных клиентов
- 50 записей телеметрии на каждое устройство

### Шаг 3: Запуск ETL в Airflow

1. Перейдите в веб-интерфейс Airflow: http://localhost:8082
2. Логин: **admin** / Пароль: **admin**
3. Найдите DAG: `etl_prosthetics_to_clickhouse`
4. Нажмите "Trigger DAG" (или включите и дождитесь расписания)
5. Дождитесь статуса **Success**

DAG извлекает данные из PostgreSQL (CRM + Telemetry), загружает в ClickHouse и пересчитывает витрину `client_telemetry_daily_mart`.

### Шаг 4: Работа с фронтендом

1. Откройте: http://localhost:3001
2. Вас перенаправит на Keycloak
3. Войдите под:
   - **Пользователь:** `client_001`
   - **Пароль:** `client123`
4. Введите дату в формате `dd-mm-yyyy`, например: `02-02-2026`
5. Нажмите **"Download Report"**

> 💡 **Совет:** Сначала проверьте доступные даты в ClickHouse (см. ниже).

- Если данные за эту дату есть — получите JSON с отчётом
- Если нет — будет ошибка: `No data available`

---

## Просмотр данных в ClickHouse

### Подключение к ClickHouse

Подключитесь через DBeaver или любой HTTP-клиент:

- **Host:** localhost
- **Port:** 8123
- **Database:** prosthetics_mart
- **User:** admin
- **Password:** admin123

### Проверка данных

SQL-запрос для проверки данных:

```sql
SELECT external_client_id, period_date, device_id, avg_battery_level, total_steps
FROM client_telemetry_daily_mart
WHERE external_client_id = 'client_001'
ORDER BY period_date DESC
LIMIT 10;
```

### Доступные таблицы


| Таблица                | Описание                                                              |
| ------------------------------- | ------------------------------------------------------------------------------- |
| `clients_dimension`           | Справочник клиентов                                         |
| `devices_dimension`           | Справочник устройств                                       |
| `telemetry_landing`           | Сырые данные с датчиков                                   |
| `client_telemetry_daily_mart` | Агрегированная витрина (источник отчётов) |

> 📝 **Примечание:** В будущем можно улучшить ETL, заменив ручной `backfill_daily_mart` на Materialized Views в ClickHouse для автоматического агрегирования.

> ⚠️ **Важно:** Данные за текущий день могут быть неполными — поэтому отчёт по сегодняшней дате может не возвращаться.

---

## Прямой запрос к бэкенду (с Bearer Token)

1. Скопируйте `access_token` из Keycloak (через DevTools → Network → Token Response)
2. Выполните GET-запрос:

```bash
curl -X GET "http://localhost:8000/report?client_id=client_001&report_date=2026-02-02" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
```

**Формат даты:** `YYYY-MM-DD`

### Пример ответа

```json
{
  "client_external_id": "client_001",
  "client_name": "Client One",
  "email": "client_001@example.com",
  "total_devices": 2,
  "reports": [...],
  "period_start": "2026-02-02",
  "period_end": "2026-02-02",
  "generated_at": "2025-04-05T12:34:56.789000"
}
```
