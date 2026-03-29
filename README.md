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
- Сервис bionicpro-auth (порт 8181): браузер ходит на localhost:8080 (Keycloak), сервер — на keycloak:8080 для token/userinfo/jwks.
- Фронт собирается с build args REACT_APP_AUTH_URL / REACT_APP_API_URL.

### Задача 4. Добавьте LDAP для возможности получения данных о пользователях.

- **OpenLDAP:** `ldap/Dockerfile` (osixia/openldap, `LDAP_DOMAIN=example.com`), данные — `ldap/config.ldif`
- Учётки из LDAP (например `jane@example.com` / `password`) доступны для входа через Keycloak

### Задача 5. Настройте MFA.

TODO

### Задача 6. Добавьте OAuth 2.0 от Яндекс ID.



