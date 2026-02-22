# Управление учётными данными пользователя — архитектурное решение

Цель: обеспечить унифицированный, безопасный и масштабируемый механизм аутентификации/авторизации пользователей BionicPRO при сохранении требований локального хранения персональных и медицинских данных.

Ключевые требования (резюме):
- не передавать access/refresh токены IdP во фронтенд;
- поддержка PKCE для публичных клиентов (frontend);
- создать централизованный session-backend `bionicpro-auth`, который хранит токены сервер-side и отдаёт фронтенду только HTTP-only Secure session cookie;
- привязка access/refresh токенов к session id и реализация ротации session id (session fixation protection);
- поддержка внешних Identity Providers (LDAP, Yandex ID и т.п.) через Keycloak Identity Brokering;
- синхронизация ролей из LDAP и маппинг в Keycloak.

Основные компоненты (контейнеры / сервисы):
- `frontend` — SPA (React). Должен убрать прямой обмен токенами с Keycloak и использовать только session cookie для вызовов API.
- `keycloak` — IdP / broker. Отвечает за federation (LDAP), MFA (OTP) и внешний brokering (Yandex ID).
- `bionicpro-auth` — новый сервис (backend):
  - реализует PKCE серверный flow: принимает код от frontend (через безопасный redirect), выполняет обмен кода на токены с Keycloak, но хранит их сервер-side;
  - хранит `access_token` и `refresh_token` в памяти/шифрованном хранилище/распределённом кеше (Redis/consul) привязанными к `session_id`;
  - выставляет клиенту HTTP-only, Secure cookie с `session_id`; cookie время жизни > lifetime `access_token`;
  - проверяет сессии при входящих запросах к защищённым ресурсам, автоматически обновляет `access_token` при его истечении, используя `refresh_token`;
  - реализует ротацию session id: при критической операции/успешной валидации перепривязывает токены к новому `session_id` и обновляет cookie;
  - предоставляет эндпоинты: `/auth/login` (инициация PKCE), `/auth/callback` (обработка кода), `/auth/logout`, `/auth/refresh`, `/auth/session` (инфо/rotate).
- `reports-api` — ресурсный бэкенд (bearerOnly client в Keycloak) — принимает запросы от frontend и валидирует сессию через `bionicpro-auth` (или проверяет session cookie и запрашивает у `bionicpro-auth` валидацию/инфо).
- `ldap` (OpenLDAP) — источник пользователей представительств; настраивается как User Federation в Keycloak.

Потоки (кратко):
1. Аутентификация (PKCE + session backend):
   - `frontend` инициирует PKCE (генерирует code_verifier, code_challenge) и перенаправляет пользователя на `bionicpro-auth` `/auth/login`;
   - `bionicpro-auth` перенаправляет на Keycloak authorization endpoint с `code_challenge` и `client_id` (frontend как public client);
   - после успешного входа Keycloak возвращает код в `bionicpro-auth` `/auth/callback`;
   - `bionicpro-auth` обменивает код на `access_token`/`refresh_token` у Keycloak (token endpoint) — токены НЕ передаются во frontend;
   - `bionicpro-auth` сохраняет токены, создаёт `session_id` и отдаёт cookie с `session_id` (HTTP-only, Secure).

2. Доступ к защищённым ресурсам:
   - `frontend` вызывает `reports-api` с cookie-сессией;
   - `reports-api` проверяет cookie у `bionicpro-auth` (внутренний проверочный endpoint) или напрямую использует shared сесс.хранилище;
   - `bionicpro-auth` валидирует `access_token` (и при необходимости обновляет его через `refresh_token`) и возвращает результат валидации/claims;
   - `reports-api` принимает решение о доступе по ролям/claims.

3. Ротация сессии (session fixation protection):
   - при успешной проверке сессии (или через конфигируемую политику) `bionicpro-auth` генерирует новый `session_id`, перепривязывает токены и переотправляет обновлённую cookie; старый `session_id` инвалидируется.

Хранение токенов и безопасность:
- `refresh_token`: хранить только на сервере в зашифрованном виде или в безопасном распределённом кеше (например, Redis с шифрованием/ACL); срок действия — конфигурируемый;
- `access_token`: хранить в памяти сервиса (или в short-lived cache) и валидировать по expiry; при истечении — использовать `refresh_token` для получения нового access token;
- все внутр. коммуникации между `bionicpro-auth` и `reports-api` должны идти по HTTPS/внутренней сети; использовать mTLS/ACL если доступно в окружении.

Keycloak и конфигурация:
- в Keycloak настроить клиента `reports-frontend` как public + PKCE (включить Authorization Code Flow with PKCE);
- оставить `reports-api` как bearerOnly или service client для валидации/интроспекции;
- установить access_token lifespan <= 2 минуты (для тестирования ротации);
- настроить LDAP Federation (с `ldap/config.ldif`) и role mappers для синхронизации ролей представительств;
- включить MFA (OTP) в Required Actions/Authentication flow для пользователей.

Поддержка внешних IdP (Yandex ID):
- использовать Identity Brokering в Keycloak. Keycloak будет получать профиль пользователя и выдавать своей локальной учетной записи; `bionicpro-auth` остаётся ответственным за сессии.