# Задача 2: Улучшение безопасности - Замена Code Grant на PKCE

## Обзор

Это решение решает проблему уязвимости в OAuth 2.0 Authorization Code Grant, которая была использована злоумышленниками для несанкционированного доступа к данным пользователей. Решение внедряет PKCE (Proof Key for Code Exchange) - расширение OAuth 2.0, которое добавляет дополнительный уровень безопасности для публичных клиентов, таких как мобильные и веб-приложения.

## Проблема

Предыдущая реализация OAuth 2.0 Code Grant была уязвима к атакам перехвата авторизационного кода (authorization code interception attacks). Злоумышленник мог перехватить код авторизации и обменять его на токены доступа, особенно в сценариях с публичными клиентами, где секрет клиента не может быть надежно сохранен.

## Решение: Внедрение PKCE

PKCE добавляет криптографическую защиту к потоку Authorization Code Grant путем использования code verifier и code challenge.

### Компоненты решения

#### 1. Frontend-приложение (Приложение для донастройки протеза)
- **Обновления**:
  - Генерация code_verifier (случайная строка)
  - Создание code_challenge из code_verifier с использованием SHA256
  - Отправка code_challenge в запросе авторизации
  - Хранение code_verifier для последующего обмена

#### 2. Keycloak (Identity Provider)
- **Обновления**:
  - Прием и хранение code_challenge при запросе авторизации
  - Валидация code_verifier при обмене кода на токены
  - Поддержка PKCE параметров в OAuth 2.0 flow

### Поток PKCE

1. **Генерация параметров**:
   ```
   Frontend генерирует:
   - code_verifier: случайная строка (43-128 символов)
   - code_challenge: base64url(SHA256(code_verifier))
   - code_challenge_method: "S256"
   ```

2. **Запрос авторизации**:
   ```
   Frontend → Keycloak:
   GET /auth?response_type=code&client_id=...&redirect_uri=...&code_challenge=...&code_challenge_method=S256
   ```

3. **Аутентификация пользователя**:
   ```
   Keycloak аутентифицирует пользователя и сохраняет code_challenge
   ```

4. **Получение кода авторизации**:
   ```
   Keycloak → Frontend: redirect_uri?code=authorization_code
   ```

5. **Обмен кода на токены**:
   ```
   Frontend → Keycloak:
   POST /token
   grant_type=authorization_code&code=...&redirect_uri=...&code_verifier=...
   ```

6. **Валидация**:
   ```
   Keycloak проверяет code_verifier против сохраненного code_challenge
   ```

### Преимущества PKCE

- **Защита от перехвата кода**: Даже если код авторизации перехвачен, без code_verifier он бесполезен
- **Безопасность публичных клиентов**: Не требует хранения секретов клиента
- **Совместимость**: PKCE обратно совместимо с существующими реализациями
- **Простота внедрения**: Минимальные изменения в существующий код

### Реализация в коде

#### Frontend (React/TypeScript)
В файле `frontend/src/App.tsx` PKCE включается через `initOptions` в `ReactKeycloakProvider`:

```typescript
const initOptions = {
  pkceMethod: 'S256'
};

const App: React.FC = () => {
  return (
    <ReactKeycloakProvider authClient={keycloak} initOptions={initOptions}>
      {/* ... */}
    </ReactKeycloakProvider>
  );
};
```

Это указывает keycloak-js использовать SHA256 для генерации code_challenge из code_verifier.

Это автоматически генерирует code_verifier и code_challenge при каждом запросе аутентификации.

#### Keycloak
Клиент "reports-frontend" настроен как публичный (`publicClient: true`) в `keycloak/realm-export.json`, что позволяет использовать PKCE без client secret:

```json
{
  "clientId": "reports-frontend",
  "enabled": true,
  "publicClient": true,
  "redirectUris": ["http://localhost:3000/*"],
  "webOrigins": ["http://localhost:3000"],
  "directAccessGrantsEnabled": true
}
```

Keycloak автоматически поддерживает PKCE для публичных клиентов начиная с версии 7.0.

### Пример реального payload с PKCE

При обмене authorization code на токены frontend отправляет `code_verifier` в теле запроса:

```
POST /auth/realms/reports-realm/protocol/openid-connect/token
Content-Type: application/x-www-form-urlencoded

code=e3c33e55-489b-458b-a313-eef5e1325c91.a9cf6d6a-df8b-48fb-b6f3-db787c4866ff.0e47c1ce-de5e-4785-aa67-70d6441839be
&grant_type=authorization_code
&client_id=reports-frontend
&redirect_uri=http://localhost:3000/
&code_verifier=pvUaRtr7usqWSFLGZWD3guKNKcRmtNDBs5AAWje26D4ernMDiyIXXHhscT0u0KF5eYhyx4cXssKzDStVREgQQYe9UIy0kuff
```

Наличие `code_verifier` подтверждает, что PKCE активен и защищает от перехвата authorization code.

### Влияние на архитектуру

- **Frontend**: Добавление логики генерации и хранения PKCE параметров
- **Keycloak**: Включение поддержки PKCE в конфигурации клиента
- **BFF Auth Service**: Может быть использован для дополнительной валидации, но PKCE обрабатывается напрямую между frontend и Keycloak

### Безопасность и соответствие

- **Улучшенная защита**: Предотвращает атаки на перехват кода
- **GDPR/локальные регуляции**: Улучшает защиту персональных данных
- **OWASP рекомендации**: Соответствует лучшим практикам OAuth 2.0