# BionicPRO Security System

Комплексная система безопасности для приложения BionicPRO с поддержкой OAuth 2.0, PKCE, MFA, LDAP и федеративной аутентификации через Яндекс ID.

## Архитектура

![Архитектурная диаграмма](architecture-diagram.drawio)

Система включает следующие компоненты:
- **bionicpro-auth** - сервис аутентификации на Python/Flask с PKCE flow
- **frontend** - React-приложение с интеграцией через auth-сервис
- **keycloak** - Identity Provider с поддержкой MFA/OTP
- **openldap** - LDAP-сервер для федеративной идентификации
- **redis** - хранилище сессий и токенов
- **postgresql** - база данных Keycloak

## Быстрый запуск

### Предварительные требования
- Docker и Docker Compose
- Свободные порты: 3000, 5000, 6379, 8080, 389, 5433

### Команды запуска

```bash
# 1. Клонируйте репозиторий и перейдите в директорию
cd /Users/nspeganov/IdeaProjects/architecture-bionicpro

# 2. Запустите все сервисы
docker-compose up -d --build

# 3. Дождитесь полной инициализации (~2 минуты)
docker-compose ps

# 4. Проверьте доступность сервисов:
# - Frontend: http://127.0.0.1:3000
# - Keycloak Admin: http://127.0.0.1:8080 (admin/admin)
# - Auth Service: http://127.0.0.1:5000/health
```

### Первый вход в систему

1. Откройте http://127.0.0.1:3000
2. Нажмите "Login with Keycloak"
3. Введите тестового пользователя: `prothetic1` / `prothetic123`
4. **Настройте OTP** (обязательно):
   - Отсканируйте QR-код в Google Authenticator или FreeOTP
   - Введите 6-значный код из приложения
5. Вы успешно вошли в систему!

## Тестовые пользователи

### Локальные пользователи:
- `prothetic1` / `prothetic123` (роль: prothetic_user)
- `prothetic2` / `prothetic123` (роль: prothetic_user)
- `admin1` / `admin123` (роль: administrator)

### LDAP пользователи (после настройки):
- `ldap_user1` / `ldapuser123` (группа: prothetic_users)
- `ldap_user2` / `ldapuser123` (группа: prothetic_users)
- `ldap_admin` / `ldapadmin123` (группа: administrators)

*Все пользователи должны настроить OTP при первом входе*

## Дополнительная настройка

### 1. Настройка LDAP User Federation
Следуйте инструкциям: [`ldap/LDAP_SETUP_INSTRUCTIONS.md`](ldap/LDAP_SETUP_INSTRUCTIONS.md)

### 2. Настройка многофакторной аутентификации (MFA)
Следуйте инструкциям: [`keycloak/MFA_OTP_SETUP_INSTRUCTIONS.md`](keycloak/MFA_OTP_SETUP_INSTRUCTIONS.md)

### 3. Интеграция с Яндекс ID
Следуйте инструкциям: [`YANDEX_ID_SETUP.md`](YANDEX_ID_SETUP.md)

### 4. Экспорт конфигурации Keycloak
Следуйте инструкциям: [`KEYCLOAK_EXPORT_INSTRUCTIONS.md`](KEYCLOAK_EXPORT_INSTRUCTIONS.md)

## Безопасность

### Реализованные меры:
✅ **PKCE (Proof Key for Code Exchange)** - защита от перехвата authorization code
✅ **Session-based Authentication** - токены не передаются на фронтенд
✅ **Short-lived Access Tokens** - TTL 2 минуты с автообновлением
✅ **Multi-Factor Authentication** - обязательный TOTP для всех пользователей
✅ **Federated Identity** - поддержка LDAP и внешних IdP
✅ **Secure Token Storage** - Redis с опциональным шифрованием
✅ **Session Rotation** - защита от session fixation атак
✅ **HTTP-only Secure Cookies** - безопасное хранение сессий

## API Endpoints

### Auth Service (bionicpro-auth:5000)
- `GET /health` - проверка состояния сервиса
- `GET /auth/login` - инициация PKCE авторизации
- `GET /auth/callback` - обработка callback от Keycloak
- `POST /auth/logout` - выход из системы
- `GET /auth/user` - получение данных пользователя
- `GET /auth/token` - получение access token для API
- `POST /auth/session/rotate` - ротация сессии

## Остановка системы

```bash
# Остановка без удаления данных
docker-compose stop

# Полная очистка (включая volumes)
docker-compose down -v
```

## Troubleshooting

### Keycloak не запускается:
```bash
docker-compose logs keycloak
docker-compose logs keycloak_db
```

### Auth-сервис не подключается:
```bash
docker-compose logs bionicpro-auth
docker-compose exec bionicpro-auth ping keycloak
```

### LDAP проблемы:
```bash
docker-compose logs openldap
# Проверьте настройки User Federation в Keycloak Admin Console
```

### Проблемы с OTP:
- Проверьте синхронизацию времени на устройстве
- Убедитесь в правильности настройки Authentication Flow
- Используйте recovery codes (если настроены)

## Технические детали

### Структура проекта:
```
.
├── bionicpro-auth/          # Auth сервис (Python/Flask)
├── frontend/                # React приложение
├── keycloak/               # Конфигурация Keycloak
├── ldap/                   # Конфигурация OpenLDAP
├── docker-compose.yaml     # Конфигурация Docker
├── architecture-diagram.drawio  # C4 диаграмма
└── README.md              # Этот файл
```

### Используемые технологии:
- **Backend**: Python 3.11, Flask, Redis, JWT
- **Frontend**: React, TypeScript, Tailwind CSS
- **Identity**: Keycloak 21.1, OpenLDAP 1.5.0
- **Database**: PostgreSQL 14
- **Infrastructure**: Docker, Docker Compose

---

Для получения подробной информации о реализации см. документацию в папке `task1/` (отчет о проделанной работе).
