# Задание 1. Повышение безопасности системы

Решение построено на паттерне **BFF (Backend-for-Frontend)**: браузер держит
только непрозрачную `HttpOnly`+`Secure` session-cookie, а все токены IdP живут на
сервере `bionicpro-auth`. Это одновременно закрывает утечку токенов (причину
взлома) и удовлетворяет требованиям всех шести задач.

## Архитектура

Диаграмма C4 (draw.io): [`docs/Task 1 Security Diagram.png`](./Task%201%20Security%20Diagram.png).

Компоненты и порты:

| Компонент        | Технология              | Порт  |
|------------------|-------------------------|-------|
| `frontend`       | React (SPA)             | 3000  |
| `bionicpro-auth` | Go (BFF)                | 8000  |
| `keycloak`       | Keycloak 21.1 (IdP)     | 8080  |
| `keycloak_db`    | PostgreSQL 14           | 5433  |
| `openldap`       | OpenLDAP (osixia 1.5)   | 389   |

## Запуск

```bash
docker compose up --build
```

- Frontend: <http://localhost:3000>
- Keycloak admin: <http://localhost:8080> (`admin` / `admin`)
- BFF health: <http://localhost:8000/healthz>

Realm импортируется автоматически из `keycloak/realm-export.json`.
LDAP бутстрапится из `ldap/config.ldif`.

## Поток аутентификации

1. SPA открывает `GET /auth/login` на BFF.
2. BFF генерирует `code_verifier`/`code_challenge` (S256) и `state`, сохраняет
   verifier на сервере, редиректит браузер на Keycloak `authorize`.
3. Пользователь проходит логин в Keycloak: логин/пароль (локальный или из LDAP)
   → **обязательный OTP** → опционально вход через **Яндекс ID**.
4. Keycloak редиректит на `GET /auth/callback?code=...&state=...`.
5. BFF меняет `code` + `code_verifier` на токены (server-to-server), создаёт
   серверную сессию, отдаёт браузеру только session-cookie и редиректит на SPA.
6. Каждый защищённый запрос (`/auth/me`, `/api/*`): BFF валидирует сессию, при
   необходимости обновляет access_token через refresh_token, **ротирует session
   id**, обновляет cookie и возвращает новый id в заголовке `X-Session-Id`.

## Соответствие задачам

### Задача 1 — архитектура управления учётными данными
- Диаграмма: `docs/task1-security.drawio`.
- Унификация доступа через внешний каталог представительства — **OpenLDAP**;
  персональные/медицинские данные хранятся локально (в стране), в Keycloak
  импортируется только то, что нужно для аутентификации/ролей.
- Токены IdP не передаются фронтенду — паттерн BFF.
- Поддержка нескольких внешних удостоверяющих служб — LDAP-федерация + Identity
  Brokering (Яндекс ID и любые OIDC/SAML IdP).

### Задача 2 — Code Grant → PKCE
- Клиент `bionicpro-auth` в Keycloak: `pkce.code.challenge.method = S256`.
- PKCE-обмен реализован в `bionicpro-auth/internal/oidc/keycloak.go`
  (`GeneratePKCE`, `AuthorizationURL`, `ExchangeCode`). Legacy-клиент
  `reports-frontend` тоже переведён на PKCE S256.

### Задача 3 — безопасное получение и хранение токенов
- Сервис `bionicpro-auth` (Go) получает access/refresh токены из Keycloak.
- `access_token` ≤ 2 мин: realm `accessTokenLifespan = 120`.
- Токены хранятся серверно (`internal/session`), привязаны к session id.
- Фронтенду отдаётся session-cookie `HttpOnly`+`Secure` (см. `COOKIE_SECURE`).
- Время жизни сессии (`SESSION_TTL=30m`) > времени access_token, авто-refresh.
- **Ротация сессии** на каждом защищённом запросе (`Store.Replace`) — защита от
  session fixation; новый id возвращается в cookie и `X-Session-Id`.
- Фронтенд больше не работает с токенами (`frontend/src/**`), только cookie
  (`credentials: 'include'`).

### Задача 4 — LDAP
- `docker-compose.yaml`: сервис `openldap`, бутстрап из `ldap/config.ldif`.
- Keycloak: User Federation (`components` в realm) ходит в `ldap://openldap:389`.
- `role-ldap-mapper` синхронизирует группы LDAP → realm-роли.

| LDAP-пользователь | Пароль     | Роль (из группы LDAP) |
|-------------------|------------|-----------------------|
| `john.doe`        | `password` | `prothetic_user`      |
| `jane.smith`      | `password` | `user`                |
| `alex.johnson`    | `password` | `prothetic_user`      |

> Исправлен баг в исходном `config.ldif`: запись `alex` имела DN `uid=alex,...`,
> тогда как группа `prothetic_user` ссылалась на `uid=alex.johnson,...`. DN
> приведён к `uid=alex.johnson,...`, иначе роль не резолвилась.

### Задача 5 — MFA (OTP)
- Realm: `otpPolicyType = totp` (Google Authenticator / FreeOTP).
- `CONFIGURE_TOTP` — default required action → обязательная настройка OTP при
  первом входе для **всех** пользователей; далее вход только после ввода OTP.

### Задача 6 — Яндекс ID (Identity Brokering)
- Realm: identity provider `yandex` (endpoints `oauth.yandex.ru`,
  `login.yandex.ru/info`), `storeToken=true`, `syncMode=IMPORT` — профиль
  запрашивается у Яндекса и сохраняется в БД Keycloak; согласие пользователя
  запрашивается механизмом first-broker-login.
