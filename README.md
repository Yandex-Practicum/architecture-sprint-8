# BionicPRO - Проектная работа 9 спринта

Проект включает улучшение архитектуры безопасности и разработку сервиса отчётов для компании BionicPRO — производителя бионических протезов.

## Структура проекта

```
├── diagrams/                    # Архитектурные диаграммы C4
│   ├── BionicPRO_C4_as-is.drawio       # Исходная архитектура
│   └── BionicPRO_C4_task1_security.drawio  # Задание 1: Архитектура безопасности
├── frontend/                    # React-приложение
├── keycloak/                    # Конфигурация Keycloak
├── ldap/                        # Конфигурация LDAP
└── docker-compose.yaml          # Docker Compose для запуска
```

---

## Задание 1. Повышение безопасности системы

### Задача 1. Архитектурное решение для управления учётными данными

**Файл:** `diagrams/BionicPRO_C4_task1_security.drawio`

#### Требования и решения:

| Требование | Решение |
|------------|---------|
| Унификация доступа через внешний источник | Keycloak как Identity Broker — федерация с внешними IdP |
| Локальное хранение персональных данных | PostgreSQL хранит медицинские данные локально в стране пользователя |
| Токены НЕ передаются фронтенду | BFF (Backend For Frontend) хранит access/refresh токены, фронтенд получает только сессионную cookie |
| Поддержка разных IdP в разных странах | Identity Federation через OIDC/SAML для России, ЕС, других рынков |

#### Ключевые компоненты архитектуры:

1. **BFF (Backend For Frontend)** — хранит токены, выдаёт сессии, проксирует запросы к API
2. **Keycloak (Identity Broker)** — федерация идентификации с внешними провайдерами
3. **Внешние IdP** — провайдеры для разных стран (ЕСИА/AD для России, Azure AD для ЕС, Okta для других)
4. **Локальная БД** — персональные и медицинские данные остаются в стране пользователя

### Задача 2. Реализация PKCE

**Файлы:**
- `keycloak/realm-export.json` — настройка PKCE для клиента
- `frontend/src/App.tsx` — использование PKCE в приложении

#### Что было изменено:

**Keycloak (realm-export.json):**
```json
{
  "clientId": "reports-frontend",
  "directAccessGrantsEnabled": false,
  "standardFlowEnabled": true,
  "attributes": {
    "pkce.code.challenge.method": "S256"
  }
}
```

**Frontend (App.tsx):**
```typescript
const initOptions = {
  pkceMethod: 'S256' as const,
  onLoad: 'check-sso' as const,
  checkLoginIframe: false
};
```

#### Как работает PKCE:

1. Frontend генерирует случайный `code_verifier`
2. Создаёт `code_challenge` = SHA256(code_verifier)
3. Отправляет `code_challenge` при запросе авторизации
4. При обмене code на токен отправляет `code_verifier`
5. Keycloak проверяет: SHA256(code_verifier) == code_challenge

Это защищает от перехвата authorization code злоумышленником.

---

## Запуск проекта

```bash
docker-compose up -d
```

- Frontend: http://localhost:3000
- Keycloak: http://localhost:8080 (admin/admin)
