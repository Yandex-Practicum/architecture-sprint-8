# architecture-bionicpro

## Задание 1. Повышение безопасности системы

### Задача 1. Предложите архитектурное решение и доработайте диаграмму C4 для управления учётными данными пользователя. 

TODO

### Задача 2. Улучшите безопасность существующего приложения, заменив Code Grant на PKCE.

- в keycloak/realm-export.json добавлен `"pkce.code.challenge.method": "S256"`
- во frontend добавлены initOptions
```
const initOptions = {
  onLoad: 'check-sso',
  pkceMethod: 'S256',
};
```

### Задача 3. Обеспечьте безопасное получение и хранение access-и refresh-токенов.

#### bionicpro-auth (Spring Boot 3.5, Gradle)
- OAuth2 Login с Keycloak (/oauth2/authorization/keycloak), после успеха токены не остаются в Spring OAuth2AuthorizedClient — они копируются в своё хранилище и клиент OAuth2 удаляется из сервиса.
- access_token — в памяти (InMemorySessionTokenStore), привязан к session id (UUID).
- refresh_token — в памяти в зашифрованном виде (AES-256-GCM, ключ из APP_ENCRYPTION_SECRET).
- Сессия — cookie BIONIC_SESSION (HttpOnly, SameSite=Lax, Secure задаётся APP_COOKIE_SECURE, в Docker для dev — false).
- Время жизни cookie — app.session-max-age-seconds (по умолчанию 1800 с > 120 с access token).
- SessionAuthenticationFilter на /api/** (кроме OPTIONS и POST /api/logout): при необходимости refresh через Keycloak, затем ротация session id (новый UUID, перенос токенов, новая cookie, заголовок X-Session-Id).
- Эндпоинты: GET /api/session, GET /api/reports, POST /api/logout.

#### Keycloak (keycloak/realm-export.json)
- Клиент bionicpro-auth (confidential, standard flow, redirect на http://localhost:8181/...).
- accessTokenLifespan: 120 (2 минуты).
- ssoSessionIdleTimeout: 1800 (30 мин).
- В Spring для refresh: scope offline_access.

#### Фронтенд
- Убраны keycloak-js и @react-keycloak/web.
- Вход: редирект на {AUTH_URL}/oauth2/authorization/keycloak.
- Все запросы к API: credentials: 'include', без Authorization с токенами в браузере.

#### Docker
- Сервис bionicpro-auth (порт 8181): браузер открывает Keycloak по **localhost:8080**; обмен кода и UserInfo из контейнера идут на **host.docker.internal:8080** (см. `docker-compose.yaml`), чтобы **issuer в JWT** (`iss`) совпадал с тем, что Keycloak ожидает при проверке токена на `/userinfo`. Для Keycloak задан **`KC_HOSTNAME=localhost`**, иначе при смешении `http://keycloak:8080` и `http://localhost:8080` возможны ошибки **`USER_INFO_REQUEST_ERROR` / `invalid_token` / Invalid token issuer**.
- Фронт собирается с build args REACT_APP_AUTH_URL / REACT_APP_API_URL.

<img src="screenshots/Task1.3_1.png" width="600">
<img src="screenshots/Task1.3_2.png" width="600">
<img src="screenshots/Task1.3_3.png" width="600">

### Задача 4. Добавьте LDAP для возможности получения данных о пользователях.

- **OpenLDAP:** `ldap/Dockerfile` (osixia/openldap, `LDAP_DOMAIN=example.com`), данные — `ldap/config.ldif`
- Учётки из LDAP (например `jane@example.com` / `password`) доступны для входа через Keycloak

<img src="screenshots/Task1.4_2.png" width="600">
<img src="screenshots/Task1.4_3.png" width="600">

### Задача 5. Настройте MFA.

<img src="screenshots/Task1.5_2.png" width="600">
<img src="screenshots/Task1.5_3.png" width="600">
<img src="screenshots/Task1.5_4.png" width="600">
<img src="screenshots/Task1.5_5.png" width="600">

### Задача 6. Добавьте OAuth 2.0 от Яндекс ID.

- **Keycloak Identity Brokering:** в `keycloak/realm-export.json` провайдер **yandex** с типом **OAuth 2.0** (`providerId: oauth2`). Указаны `authorizationUrl` / `tokenUrl` / `userInfoUrl`, scope `login:email login:info`, claim’ы профиля Яндекса (`userIDClaim: id`, `userNameClaim: login`, `emailClaim: default_email` и т.д.). Мапперы IdP переносят `default_email` → атрибут `email`, `display_name` → `firstName`. Подставьте **`YANDEX_OAUTH_CLIENT_ID`** и **`YANDEX_OAUTH_CLIENT_SECRET`** в JSON перед импортом или задайте клиент в Admin Console; в приложении Яндекса укажите redirect URI:  
  `http://localhost:8080/realms/reports-realm/broker/yandex/endpoint` (для прод — свой хост и HTTPS).
- **Вход:** на странице входа Keycloak появится кнопка входа через Яндекс; после брокера пользователь создаётся/связывается в Keycloak.
- **Согласие и БД:** сервис `bionicpro-auth` использует PostgreSQL (`auth_db`, порт **5434** на хосте), таблица `user_yandex_profile` (Flyway). После входа фронт вызывает `GET /api/profile/status`; если согласие не дано — показывается модальное окно. При согласии `POST /api/profile/consent` с `{ "accept": true }` загружает данные профиля из **Keycloak UserInfo** (куда уже попали атрибуты с Яндекса) и сохраняет в БД; при отказе — `{ "accept": false }`, запись без профиля, выход из сессии.
- **Локальный запуск без Docker:** поднимите PostgreSQL и задайте `SPRING_DATASOURCE_URL` / `USERNAME` / `PASSWORD` в `application.yml` или переменных окружения.

<img src="screenshots/Task1.6_1.png" width="600">
<img src="screenshots/Task1.6_2.png" width="600">
<img src="screenshots/Task1.6_3.png" width="600">
<img src="screenshots/Task1.6_4.png" width="600">
<img src="screenshots/Task1.6_5.png" width="600">
<img src="screenshots/Task1.6_6.png" width="600">
<img src="screenshots/Task1.6_7.png" width="600">
<img src="screenshots/Task1.6_8.png" width="600">
