# Проектная работа 9 спринта (кейс BionicPRO)
## Исходная проблема
Компанию взломали через уязвимость SSO. Утекли персональные данные пользователей. Необходимо усилить безопасность, обеспечить мультистрановую аутентификацию и изолировать доступ к данным.

## 1. Повышение безопасности системы
### 1. Предложить архитектурное решение и доработать диаграмму C4 для управления учётными данными пользователя
Для усиления безопасности системы необходимо:
- Создать новый сервис Auth Gateway - единый сервис аутентификации и авторизации, объединяющий функции BFF, IdP-роутера и менеджера токенов, который реализует в себе:
  - прием authorization code пользователей мобильного приложения и интернет-магазина
  - валидация PKCE (code_challenge / code_verifier)
  - маршрутизация аутентификации к нужному Identity Provider (IdP) в зависимости от страны пользователя
  - обмен authorization code на токены IdP
  - генерация internal JWT access token с TTL, и internal refresh token
  - валидация токенов по запросу от API-сервиса
  - refresh token rotation (одноразовое использование refresh token, старый попадает в blacklist)
- В качестве хранилища токенов использовать Redis. Хранилище реализует следующие функции:
  - хранение refresh токенов
  - хранение связки "internal refresh token → IdP refresh token"
  - token blacklist для отозванных токенов
  - автоудаление просроченных токенов по TTL
- Использовать внешние Identity Providers (за пределами системного контекста) для:
  - аутентификация через OAuth 2.0 + OIDC
  - хранения credentials пользователей происходит в соответствующем регионе
- Изменить процесс создания передачи заказа из интернет-магазина напрямую в CRM: необходимо создавать заказ в API с токеном в запросе и далее после проверки в API заказ передается в CRM

Таким образом будет реализован стандартный паттерн zero-trust архитектуры — никто не доверяет никому без токена, даже внутри периметра.

[Схема TO-BE](BionicPRO_C4_model_new.drawio)

![new_arch.png](img/new_arch.png)

### 2. Улучшить безопасность существующего приложения, заменив Code Grant на PKCE
В рамках необходимых изменений было сделано:
- **PKCE flow** реализован в бэкенде **bionicpro-auth** (Go): при редиректе на Keycloak формируются `code_verifier` и `code_challenge` (S256), при обмене кода передаётся `code_verifier` (`oauth2.GenerateVerifier`, `S256ChallengeOption`, `VerifierOption`).
- в realm для keycloak включён `standardFlowEnabled`; Keycloak принимает запросы с PKCE от confidential client.

В Keycloak 21.1 для публичных клиентов PKCE поддерживается автоматически, если клиент его использует.
Как это работает:
- bionicpro-auth при редиректе на Keycloak генерирует code_verifier и добавляет code_challenge (S256) в auth-запрос
- Keycloak принимает и сохраняет challenge
- При callback bionicpro-auth обменивает code на токены, передавая code_verifier
- Keycloak проверяет соответствие

Если нужно сделать PKCE обязательным на стороне сервера (отклонять запросы без PKCE), то это необходимо настроить через Admin Console после запуска (Realm Settings -> Client polices -> создается политика с добавлением экзекьютора pkce-enforcer).
![pkce-enforcer.png](img/pkce-enforcer.png)

### 3. Обеспечить безопасное получение и хранение access-и refresh-токенов
В рамках задания реализован сервис `bionicpro-auth` (Go): 
- интегрирован с Keycloak
  - OAuth2/OIDC Authorization Code flow
  - создан confidential client `bionicpro-auth` в Keycloak
  - задан TTL токенов: access_token TTL = 2 минуты, refresh_token TTL = 30 минут
- позволяет безопасно хранить Access-токены и Refresh-токены с помощью Redis
- привязывает токены к сессии через Session ID
- HTTP-only Secure cookies для фронта
- автоматически обновляет Access-токен через Refresh-токен по истечению TTL сессии (TTL сессии больше, чем у Access-токена)
- ротирует Session ID при каждом запросе (старый удаляется, новый создается, куки обновляется автоматически)

**API**
- `GET /auth/login` - редирект на Keycloak для авторизации
- `GET /auth/callback` - обработка OAuth callback от Keycloak
- `GET /auth/logout` - выход и очистка сессии
- `GET /auth/me` - информация о текущем пользователе
- `GET /api/reports` - прокси к API с автоматической подстановкой access_token

**Измененения фронта:**
- удалена прямая интеграция с Keycloak (keycloak-js)
- все запросы идут через бэкенд с использованием cookies
- автоматическая обработка истечения сессии

![docker1.png](img/docker1.png)

![docker2.png](img/docker2.png)

![login1.png](img/login1.png)

![login2.png](img/login2.png)

![login3.png](img/login3.png)

### 4. LDAP для пользователей представительства в другой стране

- **OpenLDAP** развёрнут в Docker (сервисы `openldap` и `ldap-bootstrap`)
- Данные пользователей и групп загружаются из **ldap/config.ldif**:
  - OU: `ou=People`, `ou=Groups`, база `dc=example,dc=com`
  - Пользователи: john.doe, jane.smith, alex.johnson (пароль `password`)
  - Группы (роли): `user`, `prothetic_user` — совпадают с именами realm roles в Keycloak для маппинга.
- Настройка Keycloak (User Federation + маппинг ролей LDAP → Realm Roles) описана в **[keycloak/LDAP-SETUP.md](keycloak/LDAP-SETUP.md)**.
- Маппинг ролей: группы LDAP `cn=user` и `cn=prothetic_user` сопоставляются с realm roles **user** и **prothetic_user**, чтобы роли разных представительств BionicPRO были едиными.

### 5. OAuth 2.0 / Identity Brokering: Яндекс ID

- Аутентификация через внешний IdP **Яндекс ID** (OAuth 2.0) настроена через Keycloak **Identity providers** (OpenID Connect v1.0 с URL Яндекса).
- Пошаговая настройка: **[keycloak/YANDEX-ID-SETUP.md](keycloak/YANDEX-ID-SETUP.md)** (регистрация приложения в Яндекс OAuth, Redirect URI для брокера, маппинг атрибутов).
- **Согласие пользователя**: для клиента **bionicpro-auth** включён **Consent Required** — после входа (в т.ч. через Яндекс) пользователь подтверждает разрешение на использование данных.
- **Сохранение профиля в БД**: сервис **bionicpro-auth** при входе через Яндекс (`identity_provider == "yandex"`) сохраняет профиль (sub, email, имя, фамилия и т.д.) в SQLite-таблицу `user_profiles` (файл задаётся через `PROFILE_DB_PATH`, по умолчанию `./data/profiles.db`; в Docker — том `./bionicpro-auth-data`).

### 6. MFA (OTP)

- Включение обязательного одноразового пароля (Google Authenticator / FreeOTP) описано в **[keycloak/MFA-SETUP.md](keycloak/MFA-SETUP.md)**.
- Шаги: дублирование потока Browser → в подпотоке Forms шаг **OTP Form** перевести в **Required** → привязать новый поток к **Browser flow** → при необходимости включить Required Action **Configure OTP** как Default action.

---

## Запуск и проверка сервисов (Docker)

1. **Поднять все сервисы** (из корня репозитория):
   ```bash
   docker compose up -d --build
   ```
   Сервисы: keycloak_db, keycloak, redis, openldap, ldap-bootstrap, bionicpro-auth, frontend.

2. **Проверить, что контейнеры запущены**:
   ```bash
   docker compose ps
   ```
   Все сервисы должны быть в состоянии `running` (ldap-bootstrap — `exited 0`).

3. **Проверка доступности** (скрипт):
   ```bash
   chmod +x scripts/verify-services.sh
   ./scripts/verify-services.sh
   ```
   Скрипт проверяет: Keycloak (http://localhost:8080), bionicpro-auth (http://localhost:8000/auth/login → 302), Frontend (http://localhost:3000), Redis (ping).

4. **Ручная проверка**:
   - Keycloak: открыть http://localhost:8080 (админ: admin / admin).
   - Вход в приложение: http://localhost:3000 → Login → редирект на Keycloak, после входа — обратно на фронт.
   - bionicpro-auth: http://localhost:8000/auth/me без cookie → 401; с сессией после логина → 200 и JSON с пользователем.

Если при сборке **bionicpro-auth** падает из‑за `go.sum`, в каталоге `bionicpro-auth` выполните `go mod tidy` и повторите `docker compose build bionicpro-auth`.

**Критерии приёмки:**

| Критерий                                             | Где                                                                                                                                      |
|------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| Диаграмма архитектуры в draw.io                      | [BionicPRO_C4_model_new.drawio](BionicPRO_C4_model_new.drawio)                                                                           |
| Код, реализующий PKCE flow                           | [bionicpro-auth/main.go](bionicpro-auth/main.go) — `handleLogin` (code_verifier, S256ChallengeOption), `handleCallback` (VerifierOption) |
| Бэкенд-сервис (access/refresh-токены, сессия)        | [bionicpro-auth/](bionicpro-auth/)                                                                                                       |
| Фронтенд работает с сессиями (без Keycloak напрямую) | [frontend/src/components/ReportPage.tsx](frontend/src/components/ReportPage.tsx) — `/auth/login`, `/auth/me`, `credentials: 'include'`   |
| Экспорт realm после настроек Keycloak                | [keycloak/keycloak-results-export.json](keycloak/keycloak-results-export.json)                                                           |
| OAuth 2.0 от Яндекс ID                               | [keycloak/YANDEX-ID-SETUP.md](keycloak/YANDEX-ID-SETUP.md), consent + сохранение профиля в bionicpro-auth                                |
