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

д) Генерация отчётов только за период, уже обработанный Airflow
Пользователь может запросить сегодняшнюю дату, а Airflow запускается раз в 6 часов или ночью

е) Запрос данных, которых ещё нет в OLAP



## Запуск

Скопируйте и заполните .env
```shell
cp frontend/.env.example frontend/.env
cp reports_api/.env.example reports_api/.env
cp .env.example .env
```

Создайте таблицы в ClickHouse
```shell
# Войти в ClickHouse клиент
docker exec -it clickhouse clickhouse-client

# Выполнить SQL из файла (или по частям)
CREATE DATABASE IF NOT EXISTS reports;

CREATE TABLE IF NOT EXISTS reports.daily_user_stats
(
    user_id              String,
    prosthesis_id        String,
    date                 Date,
    total_movements      UInt32,
    avg_signal_quality   Float32,
    min_battery_level    UInt8,
    calibration_count    UInt16,
    region               LowCardinality(String)
)
ENGINE = SummingMergeTree()
ORDER BY (user_id, date);

# Проверить, что таблица создалась
SHOW TABLES FROM reports;

# Выйти
exit;
```








