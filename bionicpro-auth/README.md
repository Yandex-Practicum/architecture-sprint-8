# bionicpro-auth

BFF/auth-сервис BionicPRO. Переносит OAuth-флоу с фронтенда на бэкенд и отдаёт
фронту только сессионную cookie.

## Возможности

- **Authorization Code Flow + PKCE (S256)** — обмен кода и токенов выполняется
  на сервере (`app/keycloak_client.py`), фронтенд в OAuth-флоу не участвует.
- **Хранение токенов** — `access_token` и `refresh_token` в Redis, привязаны к
  `session_id`; `refresh_token` шифруется (Fernet). Наружу токены не отдаются.
- **Сессионная cookie** — HttpOnly + Secure + SameSite. TTL сессии (30 мин)
  больше TTL access_token (2 мин).
- **Авто-refresh** — если `access_token` истёк, сервис сам получает новый по
  `refresh_token`.
- **Ротация session_id** — при каждом обращении к защищённому ресурсу
  (`/auth/me`, `/auth/validate`) токены перепривязываются к новому `session_id`,
  cookie обновляется (защита от session fixation).

## Эндпоинты

| Метод | Путь             | Назначение                                              |
|-------|------------------|---------------------------------------------------------|
| GET   | `/auth/login`    | старт PKCE-флоу, редирект в Keycloak                    |
| GET   | `/auth/callback` | обмен code+verifier на токены, создание сессии          |
| GET   | `/auth/me`       | данные текущего пользователя (ротирует сессию)          |
| GET   | `/auth/validate` | внутренний: проверка сессии для reports-api             |
| POST  | `/auth/logout`   | завершение сессии и SSO-сессии Keycloak                 |
| GET   | `/health`        | healthcheck                                             |

## Конфигурация

Через переменные окружения (см. `app/config.py` и `docker-compose.yaml`).
В проде задайте `COOKIE_SECURE=true` и собственный `ENCRYPTION_KEY` (Fernet,
base64 от 32 байт).
