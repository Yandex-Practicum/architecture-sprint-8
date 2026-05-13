# BionicPRO Reports System

Система для генерации отчетов по использованию протезов с микросервисной архитектурой.

### Требования

- Docker Desktop (последняя версия)
- Docker Compose v2
- 4GB+ RAM
- Порты: 3000, 389, 8000, 8080, 8081, 8123, 9000

Задание 1

1) Архитектурное решение для управления учётными данными

Текущая проблема: фронтенд работает как public OAuth client и получает токены напрямую от Keycloak. 
Вытекающие из этого проблемы:
а) Access token может быть перехвачен;
б) Refresh token хранится на устройстве;
в) Нельзя централизованно отозвать сессию;
г) Нарушается data residency (так как idp может быть в другой стране)

Что изменится
1) Унификация доступа из внешнего источника: в каждой стране поднимается региональный Keycloak, который настраивается на федерацию с локальными удостоверяющими службами (например, через SAML2 или OIDC).
2) BFF не знает о внешних IdP — он работает только с локальным Keycloak;
3) Фронтенд не знает о Keycloak, только посылает code на BFF. Фронтенд получает session_id по HttpOnly cookie и code_verifier по PKCE

Case flow

Mobile App генерирует code_verifier и code_challenge (PKCE) -> Mobile App вызывает BFF -> 
BFF Получает запрос, сохраняет code_verifier в сессии -> BFF делает редирект на Keycloak с code_challenge ->
-> Показывается страница логина Keycloak -> Пользователь вводит логин/пароль (или выбирает внешний IdP) ->
Keycloak после успешного логина редиректит на callback URL BFF с параметром code ->
BFF получает code, достаёт из сессии code_verifier -> Keycloak отдает токены взамен полученных кодов ->
BFF сохраняет access_token, refresh_token в Session Store (Redis), привязывает к session_id. Отдаёт API редирект с установкой cookie session_id (HttpOnly, Secure) ->
API во все последующие API-запросы автоматически добавляет cookie session_id через BFF -> BFF получает запрос с session_id, извлекает из Redis (или другого Key-value хранилища) access_token, прикрепляет его к запросу в Core API


RBAC (Role-Based Access Control)

В системе BionicPRO реализовано разграничение доступа на уровне API Gateway и Core API

аРоли и их права

| Роль            | Область действия          | Права                                                                                             |
|-----------------|---------------------------|---------------------------------------------------------------------------------------------------|
| user            | Свои протезы              | Чтение телеметрии, скачивание отчётов, настройка протеза через приложение                         |
| ml_engineer     | Данные всех пользователей | Доступ к анонимизированным миосигналам (без ПД) через CLI или Airflow, только для обучения модели |
| operator        | CRM / производство        | Управление заказами, статусами производства, данными о протезах (без миосигналов)                 |
| admin           | Вся система               | Полный доступ, управление пользователями, Keycloak, аудит                                         |

бПринципы

1. User видит только свои протезы — доступ к отчётам, телеметрии, настройкам ограничен по `user_id` и `prosthesis_id`.
2. ML Engineer не видит персональные данные — перед выгрузкой в ClickHouse данные обезличиваются (удаляются ФИО, контакты, адреса). Остаётся только анонимный `prosthesis_uuid` и регион.
3. Operator не имеет доступа к миосигналам — его зона ответственности только производственная и CRM-логика.
4. Admin логирует все действия — доступ к логам через централизованную систему аудита.

вРеализация

- Проверка ролей происходит в API Gateway (BFF) на основе `access_token` от Keycloak
- Keycloak управляет ролями (`realm roles` и `client roles`)
- В ClickHouse для ML-доступа используется отдельный пользователь с правами только на чтение анонимизированных таблиц


[Обновленная архитектура](images/BionicPRO_C4_model.drawio.png)

2) Замена Code Grant на PKCE

В текущей системе мобильное приложение использует Code Grant без PKCE. Это позволяет злоумышленнику, 
перехватившему authorization code, обменять его на токены, поэтому необходимо внедрить PKCE

Изменения в Keycloak

| Параметр              | Значение   |
|-----------------------|------------|
| Client ID             | mobile_app |
| Access Type           | public     |
| Standard Flow         | ON         |
| Direct Access Grants  | OFF        |

Проверка безопасности

| Угроза                                        | Без PKCE | С PKCE                  |
|-----------------------------------------------|----------|-------------------------|
| Перехват code через лог приложения            | Уязвимо  | Бесполезно без verifier |
| Вредоносное приложение, перехватившее Intent  | Уязвимо  | Verifier в хранилище    |

- Мобильное приложение генерирует code_verifier и сохраняет в protected storage (Keychain/Keystore)
- При старте логина передаётся code_challenge = BASE64URL(SHA256(code_verifier))
- При обмене code на токены передаётся code_verifier
- Keycloak проверяет соответствие code_challenge и code_verifier

Результат - при перехвате code злоумышленник не может получить токены без code_verifier


2) Построение витрины (в Airflow, после загрузки CRM)

CREATE TABLE default.daily_user_stats
(
    user_id          String,
    prosthesis_id    String,
    date             Date,
    region           LowCardinality(String),
    total_movements  UInt32,
    avg_signal_quality Float32,
    battery_drain_pct UInt8,
    calibration_count UInt16
) ENGINE = SummingMergeTree()
ORDER BY (user_id, date);

Запрос отчёта
Mobile App -> BFF (session_id) -> Report API (проверка user_id из токена) -> 
SELECT * FROM daily_user_stats WHERE user_id = ? AND date BETWEEN ? AND ? -> возврат JSON (или генерация PDF)

Проверки

а) UI позволяет вызвать API для генерации отчётов

б) Неаутентифицированный пользователь не может сгенерировать отчёт
В ReportPage.tsx есть проверка, что без логина кнопка "Download Report" не показывается.
```
if (!keycloak.authenticated) {
  return <button onClick={() => keycloak.login()}>Login</button>;
}
```

в) Авторизованный пользователь может сгенерировать только свой отчёт
В reports-api/app/routers/reports.py есть проверка
```
if "administrator" not in current_user["roles"]:
    if current_user["username"] != user_id:
        raise HTTPException(status_code=403)
```

г) Сервис запрашивает отчёт из OLAP (ClickHouse)
Да

д) Генерация отчётов только за период, уже обработанный Airflow
да.будет ошибка, если выбрать сегодняшнюю или будущую дату

е) Запрос данных, которых ещё нет в OLAP
Будет ошибка

## Запуск
Создайте файл .env в корне проекта:
```shell
cp .env.example .env
```
Отредактируйте .env при необходимости (стандартные настройки уже работают)

Запустите систему

```shell
docker compose up -d
```

Проверка работы
```shell
# Проверить статус всех сервисов
docker compose ps

# Должны быть все "Up" или "running"

# Проверить ClickHouse
docker exec -it clickhouse clickhouse-client --query "SELECT COUNT(*) FROM reports.daily_user_stats"
# Должно вернуть: 6

# Проверить API
curl http://localhost:8000/health
# Должно вернуть: {"status":"ok"}
```

Тестовые пользователи

| Username   | Password     | Роль                 |
|------------|--------------|----------------------|
| prothetic1 | prothetic123 | Пользователь протеза |
| prothetic2 | prothetic123 | Пользователь протеза |
| prothetic3 | prothetic123 | Пользователь протеза |
| user1      | password123  | Обычный пользователь |
| user2      | password123  | Обычный пользователь |
| admin1     | admin123     | Администратор        |

Для получения отчета через Web UI откройте http://localhost:3000, залогиньтесь одним из пользователей, выберите даты и скачайте отчет
Нельзя выбрать сегодняшнюю или будущую даты, так как отчет не сформируется ввиду отсутствия данных
После выбора дат нажмите на кнопку "Download Report"

Тестирование через терминал

```shell
# Получить токен
TOKEN=$(curl -s -X POST http://localhost:8080/realms/reports-realm/protocol/openid-connect/token \
  -d "client_id=reports-frontend" \
  -d "username=prothetic1" \
  -d "password=prothetic123" \
  -d "grant_type=password" | jq -r '.access_token')

# Запросить отчет
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports/prothetic1?from_date=2026-05-06&to_date=2026-05-11" | jq '.'
```

Получить свой отчет
```shell
# Получить токен для prothetic1
TOKEN=$(curl -s -X POST http://localhost:8080/realms/reports-realm/protocol/openid-connect/token \
  -d "client_id=reports-frontend" \
  -d "username=prothetic1" \
  -d "password=prothetic123" \
  -d "grant_type=password" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")

echo "Token получен: ${TOKEN:0:50}..."

# Запросить СВОЙ отчет (должно работать)
echo "=== Тест 1: Запрос своего отчета ==="
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports/prothetic1?from_date=2026-05-06&to_date=2026-05-11" | python3 -m json.tool | head -20
```

Получить чужой отчет (должен вернуть 403 Forbidden)

```shell
# Запросить ЧУЖОЙ отчет (должно быть запрещено)
echo ""
echo "=== Тест 2: Запрос чужого отчета (должен вернуть 403) ==="
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports/prothetic2?from_date=2026-05-06&to_date=2026-05-11" | python3 -m json.tool
```

Администратор может видеть все отчеты

```shell
# Получить токен администратора
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8080/realms/reports-realm/protocol/openid-connect/token \
  -d "client_id=reports-frontend" \
  -d "username=admin1" \
  -d "password=admin123" \
  -d "grant_type=password" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")

echo ""
echo "=== Тест 3: Администратор запрашивает чужой отчет (должен работать) ==="
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/reports/prothetic1?from_date=2026-05-06&to_date=2026-05-11" | python3 -m json.tool | head -20
```

Будущие даты (должен вернуть ошибку)

```shell
# Запросить будущие даты (должно быть запрещено)
FUTURE_DATE=$(date -v+5d +%Y-%m-%d 2>/dev/null || date -d "+5 days" +%Y-%m-%d)
echo ""
echo "=== Тест 4: Запрос будущих дат (должен вернуть 400) ==="
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports/prothetic1?from_date=2026-05-06&to_date=$FUTURE_DATE" | python3 -m json.tool
```


Структура базы данных

| Поле               | Тип     | Описание                  |
|--------------------|---------|---------------------------|
| user_id            | String  | ID пользователя           |
| prosthesis_id      | String  | ID протеза                |
| date               | Date    | Дата                      |
| total_movements    | UInt32  | Количество движений       |
| avg_signal_quality | Float32 | Среднее качество сигнала  |
| min_battery_level  | UInt8   | Минимальный заряд батареи |
| calibration_count  | UInt16  | Количество калибровок     |
| region             | String  | Регион                    |


