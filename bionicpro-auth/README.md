# bionicpro-auth — session broker (skeleton)

Лёгкий skeleton сервиса `bionicpro-auth` на FastAPI. Предназначен как серверная прослойка для PKCE flow и хранения токенов server-side.

Основные endpoints:
- `GET /auth/login` — инициирует PKCE/authorize redirect на Keycloak
- `GET /auth/callback` — callback, обмен кода на токены, создание session
- `POST /auth/refresh` — обновление access_token по refresh_token
- `POST /auth/logout` — инвалидация сессии
- `GET /session/validate` — проверка session (используется `reports-api`)

Запуск локально (при наличии docker-compose):

```bash
docker compose up --build
```

Переменные окружения (в `docker-compose.yaml` предоставлены примеры):
- `KEYCLOAK_URL` (пример: http://keycloak:8080)
- `KEYCLOAK_REALM`
- `CLIENT_ID` (публичный клиент frontend)
- `CALLBACK_URL` (например: http://bionicpro-auth:8000/auth/callback)
- `FRONTEND_URL` (куда перенаправлять после логина)
- `REDIS_URL` (опционально)

Это skeleton для разработки — в production нужно добавить шифрование refresh_token, TLS, ACL и т.п.
