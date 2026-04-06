# Инструкция по настройке MFA (OTP) в Keycloak

## Обзор
Многофакторная аутентификация (MFA) добавляет дополнительный уровень безопасности, требуя от пользователей вводить одноразовый пароль (OTP) в дополнение к стандартным учетным данным.

## Предварительные требования
- Keycloak запущен и доступен
- Realm "reports-realm" настроен
- Мобильное приложение для OTP (Google Authenticator или FreeOTP)

## Шаг 1: Настройка OTP в Realm Settings

1. Войдите в Keycloak Admin Console (http://127.0.0.1:8080)
2. Выберите realm "reports-realm"
3. Перейдите в "Realm Settings" → "Security Defenses" → "OTP Policy"

### Настройте параметры OTP:
- **OTP Type**: Time-Based (TOTP)
- **OTP Hash Algorithm**: SHA1
- **Number of Digits**: 6
- **Look Ahead Window**: 1
- **OTP Token Period**: 30 секунд
- **Supported Applications**: FreeOTP, Google Authenticator

4. Сохраните настройки

## Шаг 2: Настройка Authentication Flow с OTP

1. Перейдите в "Authentication" → "Flows"
2. Создайте новый flow или скопируйте существующий "Browser" flow
3. Нажмите "Copy" на "Browser" flow, назовите его "Browser with OTP"

### Настройте flow:
1. В "Browser with OTP" flow найдите "Browser - Conditional OTP"
2. Измените требование на **REQUIRED** для "OTP Form"
3. Убедитесь, что структура следующая:
   ```
   Browser with OTP (FLOW)
   ├── Cookie (ALTERNATIVE)
   ├── Identity Provider Redirector (ALTERNATIVE)
   └── Forms (ALTERNATIVE)
       ├── Username Password Form (REQUIRED)
       └── Browser - Conditional OTP (CONDITIONAL)
           ├── Condition - User Configured (REQUIRED)
           └── OTP Form (REQUIRED)
   ```

4. Привяжите flow к realm:
   - "Realm Settings" → "Authentication" → "Bindings"
   - **Browser Flow**: Browser with OTP
   - Сохраните

## Шаг 3: Настройка Required Actions для всех пользователей

### Вариант A: Для новых пользователей (через realm settings)
1. Перейдите в "Authentication" → "Required Actions"
2. Найдите "Configure OTP"
3. Установите "Default Action" в ON
4. Сохраните

### Вариант B: Для существующих пользователей (массово)
1. Перейдите в "Users" → "View all users"
2. Для каждого пользователя:
   - Откройте профиль пользователя
   - Перейдите во вкладку "Credentials"
   - Нажмите "Required User Actions"
   - Выберите "Configure OTP"
   - Сохраните

### Вариант C: Через realm configuration (уже включено в JSON)
В файле `realm-export-updated.json` уже настроено:
```json
"requiredActions": ["CONFIGURE_TOTP"]
```

## Шаг 4: Тестирование MFA

### Первый вход пользователя:
1. Откройте приложение: http://127.0.0.1:3000
2. Нажмите "Login"
3. Введите credentials (например, prothetic1 / prothetic123)
4. Keycloak перенаправит на страницу настройки OTP
5. Отсканируйте QR-код с помощью Google Authenticator или FreeOTP
6. Введите 6-значный код из приложения
7. Подтвердите настройку

### Последующие входы:
1. Введите username и password
2. Введите текущий OTP код из приложения
3. Успешная аутентификация

## Шаг 5: Управление OTP для пользователей

### Сброс OTP для пользователя (Admin):
1. "Users" → выберите пользователя
2. "Credentials" → найдите "OTP"
3. Нажмите "Delete" для сброса
4. Пользователь будет вынужден настроить OTP заново

### Проверка статуса OTP:
1. В профиле пользователя во вкладке "Credentials"
2. Проверьте наличие "OTP" в списке credentials

## Шаг 6: Настройка политик OTP (опционально)

### Увеличение безопасности:
1. "Realm Settings" → "Security Defenses" → "OTP Policy"
2. Измените параметры:
   - **OTP Hash Algorithm**: SHA256 (более безопасный)
   - **Number of Digits**: 8 (больше комбинаций)
   - **Look Ahead Window**: 0 (строже)

## Резервные коды восстановления (Recovery Codes)

### Включение recovery codes:
1. "Authentication" → "Required Actions"
2. Включите "Configure Recovery Authentication Codes"
3. Users получат набор одноразовых кодов восстановления

## Тестирование с разными пользователями

### Локальные пользователи:
- prothetic1 / prothetic123
- prothetic2 / prothetic123
- admin1 / admin123

### LDAP пользователи:
- ldap_user1 / ldapuser123
- ldap_admin / ldapadmin123

Все эти пользователи должны настроить OTP при первом входе.

## Troubleshooting

### OTP не работает:
1. Проверьте время на сервере и на устройстве (должно быть синхронизировано)
2. Убедитесь, что OTP Type = Time-Based
3. Проверьте период токена (30 секунд по умолчанию)

### Пользователь не видит страницу настройки OTP:
1. Проверьте Required Actions в профиле пользователя
2. Убедитесь, что Browser Flow правильно настроен
3. Проверьте логи Keycloak

### Невозможно войти после настройки OTP:
1. Используйте recovery codes (если включены)
2. Администратор может сбросить OTP credentials
3. Проверьте синхронизацию времени

## Рекомендации по безопасности

1. Всегда используйте TOTP (Time-Based) вместо HOTP (Counter-Based)
2. Используйте SHA256 для production
3. Не отключайте OTP после включения
4. Регулярно напоминайте пользователям о безопасности OTP кодов
5. Включите recovery codes для восстановления доступа
6. Ограничьте количество попыток ввода OTP
