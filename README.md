# BionicPRO - Комплексная система безопасности и аналитики

Полнофункциональная система для BionicPRO с поддержкой OAuth 2.0, PKCE, MFA, LDAP, федеративной аутентификации и аналитической системы отчетов на базе Apache Airflow и ClickHouse.

## Архитектура

![Архитектурная диаграмма](architecture-diagram.drawio)

### Компоненты безопасности (Task 1)
- **bionicpro-auth** - сервис аутентификации на Python/Flask с PKCE flow
- **frontend** - React-приложение с интеграцией через auth-сервис
- **keycloak** - Identity Provider с поддержкой MFA/OTP
- **openldap** - LDAP-сервер для федеративной идентификации
- **redis** - хранилище сессий и токенов
- **postgresql** - база данных Keycloak

### Компоненты аналитики (Task 2)
- **reports-api** - FastAPI сервис для получения отчетов с JWT авторизацией
- **apache-airflow** - оркестрация ETL процессов (веб-сервер, планировщик)
- **clickhouse** - колоночная OLAP база данных для аналитики
- **crm_db** - PostgreSQL база данных CRM-системы
- **airflow_db** - PostgreSQL база метаданных Airflow

## Быстрый запуск

### Предварительные требования
- Docker и Docker Compose
- Минимум 8 GB RAM для Docker
- Свободные порты: 3000, 5000, 6379, 8000, 8080, 8081, 8123, 9000, 389, 5433-5435

### Команды запуска

```bash
# 1. Клонируйте репозиторий и перейдите в директорию
cd /Users/nspeganov/IdeaProjects/architecture-bionicpro

# 2. Запустите все сервисы
docker-compose up -d --build

# 3. Дождитесь полной инициализации (~3-5 минут)
docker-compose ps

# 4. Настройте Airflow connections (опционально)
bash airflow/setup-connections.sh

# 5. Запустите ETL процесс в Airflow
# Откройте http://127.0.0.1:8081 (admin/admin)
# Включите и запустите DAG 'etl_crm_to_clickhouse'

# 6. Проверьте доступность сервисов:
# - Frontend: http://127.0.0.1:3000
# - Keycloak Admin: http://127.0.0.1:8080 (admin/admin)
# - Auth Service: http://127.0.0.1:5000/health
# - Reports API: http://127.0.0.1:8000/health
# - Airflow UI: http://127.0.0.1:8081 (admin/admin)
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

### Reports API (reports-api:8000)
- `GET /` - информация о сервисе
- `GET /health` - проверка подключения к ClickHouse
- `GET /reports` - получение отчетов пользователя (требует JWT)
- `GET /reports/summary` - сводная статистика (требует JWT)
- `GET /docs` - Swagger документация API

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
- **Backend**: Python 3.11, Flask, FastAPI, Redis, JWT
- **Frontend**: React, TypeScript, Tailwind CSS
- **Identity**: Keycloak 21.1, OpenLDAP 1.5.0
- **Database**: PostgreSQL 14, ClickHouse 23.8
- **ETL**: Apache Airflow 2.9.1
- **Infrastructure**: Docker, Docker Compose

## Документация по задачам

### Task 1: Система безопасности
См. подробную документацию в папке `task1/`:
- [Отчет о выполнении](task1/TASK1_COMPLETION_REPORT.md)
- [Быстрый старт](task1/QUICKSTART.md)

Реализовано:
- ✅ PKCE Flow для защиты авторизации
- ✅ Session-based аутентификация
- ✅ Многофакторная аутентификация (OTP)
- ✅ LDAP интеграция
- ✅ Федеративная аутентификация (Яндекс ID)

### Task 2: Система отчетов
См. подробную документацию в папке `task2/`:
- [Отчет о выполнении](task2/TASK2_COMPLETION_REPORT.md)
- [Быстрый старт](task2/QUICKSTART.md)
- [Архитектурная диаграмма](task2/architecture-diagram.puml)

Реализовано:
- ✅ ETL процесс на Apache Airflow
- ✅ OLAP хранилище на ClickHouse
- ✅ Витрина данных для отчетов
- ✅ Reports API с JWT авторизацией
- ✅ UI для получения отчетов
- ✅ RBAC - доступ только к своим данным

---

## Архитектура проекта

```
┌──────────────────────────────────────────────────────────────┐
│                         User                                  │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         v
┌────────────────────────────────────────────────────────────────┐
│                      Frontend (React)                          │
│  - Login with Keycloak                                         │
│  - Session management                                          │
│  - Reports UI                                                  │
└─────────┬──────────────────────────────────────┬───────────────┘
          │                                      │
          │ Session                             │ Bearer token
          │                                      │
          v                                      v
┌──────────────────────┐              ┌──────────────────────┐
│   Auth Service       │              │    Reports API       │
│   (Flask + PKCE)     │              │    (FastAPI)         │
└──────┬───────────────┘              └──────┬───────────────┘
       │                                      │
       │                                      │
       v                                      v
┌──────────────────────┐              ┌──────────────────────┐
│    Keycloak IdP      │              │    ClickHouse        │
│    + LDAP            │              │    (OLAP)            │
└──────────────────────┘              └──────▲───────────────┘
                                             │
                                             │ ETL
                                             │
                                      ┌──────┴───────────────┐
                                      │   Apache Airflow     │
                                      │   DAG Scheduler      │
                                      └──────▲───────────────┘
                                             │
                                             │ Extract
                                             │
                                      ┌──────┴───────────────┐
                                      │   CRM Database       │
                                      │   (PostgreSQL)       │
                                      └──────────────────────┘
```
