# BionicPRO — Отчёт о выполнении заданий

## Задание 1. Повышение безопасности системы

### Задача 1.1. Архитектура Federated Identity + BFF

**Цель:** Предложить архитектуру для унификации доступа с учётом локального хранения данных в разных странах.

**Изменённые файлы:**

- `BionicPRO_C4_model.drawio.xml` — добавлены контейнеры и связи:
  - **Keycloak (SSO Server)** — центральный IdP
  - **Token Proxy / BFF** — сервер-посредник для безопасного хранения токенов
  - **Federated Identity Provider** — внешние удостоверяющие службы
  - Связи: Federated IdP → Keycloak (SAML/OIDC) → BFF (Code + PKCE) → API (JWT)

#### Компоненты архитектуры

**1. Keycloak (центральный IdP)**

- Роль: единый провайдер аутентификации и авторизации (SSO)
- Протоколы: OpenID Connect, OAuth 2.0
- Хранение: локальная база PostgreSQL для конфигурации Realm
- Пользователи: федеративные — через User Federation (LDAP), внешние — через SAML/OIDC Identity Providers

**2. LDAP / Active Directory (User Federation)**

- Роль: локальное хранение учётных записей сотрудников в каждой стране
- Механизм: Keycloak подключает LDAP-каталог как User Federation провайдера
- Преимущества: пароли и атрибуты не покидают страну, проверка учётных данных — на стороне LDAP, поддержка OU (People, Groups)
- Конфигурация: `ldap/config.ldif` — тестовые пользователи и группы

**3. Federated Identity Provider (внешние IdP)**

- Роль: аутентификация пользователей через внешние удостоверяющие службы в разных странах
- Протоколы: SAML 2.0, OpenID Connect
- Сценарий: Keycloak выступает как Service Provider (SP), внешний IdP — как Identity Provider
- Data residency: токены и атрибуты подтверждаются внешним IdP, персональные данные хранятся локально

**4. Token Proxy / BFF (Backend-for-Frontend)**

- Роль: промежуточный сервис между SPA-фронтендом и Keycloak/API
- Безопасность: фронтенд никогда не получает access/refresh токены напрямую от IdP
- Протокол: SPA → BFF через httpOnly session cookie (недоступна JavaScript)
- Жизненный цикл токенов:
  - BFF выполняет Authorization Code + PKCE flow с Keycloak
  - Access/Refresh токены хранятся в серверной сессии BFF
  - BFF проксирует запросы к API, подставляя JWT из сессии
  - Refresh токена происходит прозрачно на стороне BFF

#### Потоки аутентификации

**Внутри страны (Local)**

```
Пользователь → SPA → BFF (session cookie)
                         ↓
                    Keycloak ←→ LDAP (User Federation)
                         ↓
                    BFF хранит токены в сессии (httpOnly)
                         ↓
                    BFF → API (JWT)
```

**Между странами (Federated)**

```
Пользователь (Страна A) → SPA → BFF
                                   ↓
                              Keycloak (SP)
                                   ↓
                   ╔══════════════════════╗
                   ║ Federated IdP        ║
                   ║ (Страна B)           ║
                   ║ SAML/OIDC            ║
                   ╚══════════════════════╝
                                   ↓
                              Keycloak получает атрибуты
                              Данные хранятся локально в Стране A
```

#### Data Residency (границы хранения данных)

| Тип данных | Где хранится | Обоснование |
|-----------|-------------|-------------|
| Персональные данные (ФИО, паспорт) | LDAP в стране пользователя | 152-ФЗ, GDPR |
| Медицинские данные телеметрии | PostgreSQL в стране пользователя | Медицинская тайна |
| Учётные данные (пароли) | LDAP / AD локально | Никогда не покидают страну |
| Метаданные сессии | BFF (сервер в стране пользователя) | Временные данные |
| Агрегированная аналитика | ClickHouse (OLAP) | Обезличенные данные |

#### Требования безопасности

1. PKCE — обязателен для всех публичных клиентов (SPA, мобильное приложение)
2. BFF — токены никогда не попадают в браузер пользователя
3. httpOnly session cookie — защита от XSS
4. CORS — строгая политика (не `*`)
5. LDAPS — шифрование трафика между Keycloak и LDAP
6. JWT Validation — проверка подписи RS256 на BFF при проксировании

---

### Задача 1.2. Переход с Code Grant на PKCE

**Цель:** Улучшить безопасность аутентификации для публичных клиентов (SPA).

**Изменённые файлы:**

- `keycloak/realm-export.json`:
  - Добавлен `"attributes": { "pkce.code.challenge.method": "S256" }` для клиента `reports-frontend`
  - Отключён `directAccessGrantsEnabled` (`true` → `false`)

**Обоснование:**

- **PKCE (S256)** — обязателен для публичных клиентов (SPA). Без него authorization code можно перехватить. В Keycloak 21.1 настраивается через `attributes` в JSON-экспорте.
- **Direct Access Grants отключён** — ROPC-flow небезопасен для SPA, заменён на PKCE + Authorization Code.
- **keycloak-js v21.1** — PKCE поддерживается нативно, фронтенд менять не пришлось.

**Проверка:** Keycloak запущен, realm `reports-realm` импортирован, PKCE S256 подтверждён через Admin API (`attributes.pkce.code.challenge.method: "S256"`).
