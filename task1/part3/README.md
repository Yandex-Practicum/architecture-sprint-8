# Задача 3: Безопасное получение и хранение access- и refresh-токенов

## Обзор решения

В данной задаче реализован безопасный механизм аутентификации и авторизации для приложения BionicPRO с использованием Keycloak как Identity Provider. Основные компоненты:

- **Backend сервис (Python/FastAPI)**: Обработка OAuth2 flow, управление сессиями, хранение токенов
- **Keycloak**: Identity Provider с настроенными клиентами и политиками токенов
- **Frontend (React)**: Простой интерфейс с использованием сессионных cookies
- **Redis**: Хранение access токенов
- **Шифрование**: Refresh токены хранятся в зашифрованном виде

## Архитектура

### Компоненты

1. **Keycloak (OIDC Provider)**
   - Realm: `reports-realm`
   - Client: `reports-api` (confidential)
   - Access token lifespan: 2 минуты
   - Refresh token: включен

2. **Backend сервис (Python/FastAPI)**
   - Порт: 8081
   - Endpoints:
     - `GET /auth/login` - Инициирует OAuth2 flow
     - `GET /auth/callback` - Обрабатывает callback от Keycloak
     - `GET /api/protected` - Проверяет аутентификацию
     - `GET /api/reports` - Возвращает отчеты (защищенный ресурс)
     - `POST /auth/logout` - Выход из системы

3. **Frontend (React)**
   - Использует сессионные cookies для аутентификации
   - Автоматическая проверка статуса аутентификации

4. **Хранилище**
   - **Redis**: Access токены (с TTL 2 минуты)
   - **Оперативная память**: Зашифрованные refresh токены
   - **Cookies**: Session ID (HTTP-only, Secure, SameSite=strict)

### Безопасность

#### Токены
- **Access token**: Хранится в Redis с TTL = 2 минуты
- **Refresh token**: Шифруется с помощью Fernet и хранится в памяти
- **Автоматическое обновление**: При истечении access token сервис автоматически обновляет его через refresh token

#### Сессии
- **Session ID**: Генерируется как UUID4
- **Ротация сессии**: При каждом запросе к защищенному ресурсу генерируется новый session ID
- **Cookies**: HTTP-only, Secure, SameSite=strict, max-age=1 час

#### Защита от атак
- **Session fixation**: Ротация session ID предотвращает фиксацию сессии
- **Token leakage**: Токены не передаются в frontend, только session cookies
- **CSRF**: SameSite=strict cookies защищают от CSRF

## API Endpoints

### Аутентификация
- `GET /auth/login` → Redirect to Keycloak
- `GET /auth/callback?code=...&state=...` → Exchange code for tokens, create session
- `POST /auth/logout` → Revoke tokens, destroy session

### Защищенные ресурсы
- `GET /api/protected` → Check authentication (rotates session)
- `GET /api/reports` → Get reports (rotates session)

## Flow аутентификации

1. Пользователь кликает "Login" → Redirect to `/auth/login`
2. Backend redirects to Keycloak auth URL
3. Keycloak показывает login form
4. После успешного логина → Redirect to `/auth/callback` с authorization code
5. Backend обменивает code на access + refresh tokens
6. Refresh token шифруется и сохраняется в памяти
7. Access token сохраняется в Redis
8. Устанавливается session cookie
9. Frontend получает session ID и может делать запросы к защищенным ресурсам

## Автоматическое обновление токенов

При каждом запросе к защищенному ресурсу:
1. Проверяется наличие access token в Redis
2. Если отсутствует → Используется refresh token для получения новых токенов
3. Новые токены сохраняются
4. Ротация session ID для предотвращения session fixation

## Мониторинг и логирование

- Логи Keycloak: `docker-compose logs keycloak`
- Логи Backend: `docker-compose logs bionicpro-auth`
- Redis: `docker-compose exec redis redis-cli`

## Тестирование

1. Открыть http://localhost:3000
2. Кликнуть "Login"
3. Войти как user1/password123
4. Проверить доступ к отчетам
5. Подождать 2 минуты, сделать запрос - токен обновится автоматически