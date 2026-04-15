# Настройка OAuth 2.0 от Яндекс ID через Identity Brokering в Keycloak

## Обзор
Identity Brokering позволяет Keycloak делегировать аутентификацию внешним провайдерам (Identity Providers), таким как Яндекс ID. Пользователи могут входить через Яндекс аккаунт, а их данные будут автоматически синхронизированы с Keycloak.

## Предварительные требования
1. Аккаунт Яндекс ID для разработки
2. Зарегистрированное приложение в Yandex OAuth

## Шаг 1: Регистрация приложения в Яндекс OAuth

### 1.1. Перейдите на https://oauth.yandex.ru/
1. Войдите с вашим Яндекс аккаунтом
2. Нажмите "Создать новое приложение"

### 1.2. Заполните форму регистрации:
- **Название**: BionicPRO Authentication
- **Платформы**: Выберите "Веб-сервисы"
- **Redirect URI**:
  ```
  http://127.0.0.1:8080/realms/reports-realm/broker/yandex/endpoint
  ```

  (Для production замените 127.0.0.1 на ваш домен)

### 1.3. Права доступа (Scopes):
Выберите необходимые разрешения:
- ✅ **login:email** - Доступ к email адресу
- ✅ **login:info** - Доступ к имени и полу
- ✅ **login:avatar** - Доступ к аватару пользователя

### 1.4. Сохраните учетные данные:
После создания приложения вы получите:
- **Client ID** (ID приложения) - например: `1234567890abcdef`
- **Client Secret** (Пароль приложения) - например: `secret_key_here`

**ВАЖНО**: Сохраните эти данные - они понадобятся для настройки Keycloak.

## Шаг 2: Настройка Identity Provider в Keycloak

### 2.1. Войдите в Keycloak Admin Console
1. Откройте http://127.0.0.1:8080
2. Войдите: admin / admin
3. Выберите realm "reports-realm"

### 2.2. Добавьте Identity Provider
1. В левом меню выберите **Identity Providers**
2. Из выпадающего списка "Add provider" выберите **OpenID Connect v1.0**
   (Яндекс ID поддерживает OpenID Connect)

### 2.3. Конфигурация провайдера:
Заполните следующие поля:

#### General Settings:
- **Alias**: `yandex` (используется в URL)
- **Display Name**: `Яндекс ID`
- **Enabled**: ON
- **Store Tokens**: ON (сохранять токены от Яндекса)
- **Stored Tokens Readable**: ON
- **Trust Email**: ON (доверять email от Яндекса)
- **First Login Flow**: first broker login

#### OpenID Connect Config:
- **Authorization URL**:
  ```
  https://oauth.yandex.ru/authorize
  ```

- **Token URL**:
  ```
  https://oauth.yandex.ru/token
  ```

- **User Info URL**:
  ```
  https://login.yandex.ru/info
  ```

- **Client Authentication**: Client secret sent as post
- **Client ID**: `<ваш Client ID из Яндекс OAuth>`
- **Client Secret**: `<ваш Client Secret из Яндекс OAuth>`

- **Default Scopes**:
  ```
  login:email login:info login:avatar
  ```

- **Prompt**: unset (или `consent` для запроса согласия)
- **Accepts prompt=none forward from client**: OFF
- **Disable User Info**: OFF
- **Validate Signatures**: OFF (Яндекс не предоставляет JWKS)
- **Use PKCE**: OFF (опционально, можно включить для дополнительной безопасности)

#### Advanced Settings:
- **Pass Login Hint**: OFF
- **Pass current locale**: ON
- **Sync Mode**: IMPORT (импорт пользователей из Яндекса)

### 2.4. Сохраните конфигурацию
Нажмите "Save" внизу страницы.

## Шаг 3: Настройка Mappers для синхронизации данных

Mappers определяют, как данные из Яндекс ID маппятся на атрибуты пользователя в Keycloak.

### 3.1. Перейдите во вкладку "Mappers"
1. Нажмите "Create"
2. Создайте следующие mappers:

#### Mapper 1: Email
- **Name**: email
- **Sync Mode Override**: IMPORT
- **Mapper Type**: Attribute Importer
- **Claim**: default_email
- **User Attribute Name**: email

#### Mapper 2: First Name
- **Name**: first_name
- **Sync Mode Override**: IMPORT
- **Mapper Type**: Attribute Importer
- **Claim**: first_name
- **User Attribute Name**: firstName

#### Mapper 3: Last Name
- **Name**: last_name
- **Sync Mode Override**: IMPORT
- **Mapper Type**: Attribute Importer
- **Claim**: last_name
- **User Attribute Name**: lastName

#### Mapper 4: Username
- **Name**: username
- **Sync Mode Override**: IMPORT
- **Mapper Type**: Attribute Importer
- **Claim**: login
- **User Attribute Name**: username

#### Mapper 5: Avatar (опционально)
- **Name**: avatar
- **Sync Mode Override**: IMPORT
- **Mapper Type**: Attribute Importer
- **Claim**: default_avatar_id
- **User Attribute Name**: avatar

## Шаг 4: Интеграция с базой данных для сохранения профилей

Keycloak автоматически создаст пользователя при первом входе через Яндекс. Если нужно дополнительно сохранять данные в отдельной БД:

### 4.1. Создайте таблицу для профилей:
```sql
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    keycloak_user_id VARCHAR(255) UNIQUE NOT NULL,
    yandex_user_id VARCHAR(255),
    email VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    avatar_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2. Event Listener (опционально)
Можно настроить Event Listener в Keycloak для автоматического сохранения данных в БД при регистрации через Яндекс.

## Шаг 5: Настройка запроса согласия пользователя

### 5.1. Включите Consent Screen:
1. Вернитесь к Identity Provider "yandex"
2. В разделе "Advanced Settings" найдите:
   - **GUI Order**: 1 (порядок отображения)
   - **First Login Flow**: first broker login
3. Сохраните

### 5.2. Настройте First Broker Login Flow:
1. Перейдите в "Authentication" → "Flows"
2. Выберите "First Broker Login"
3. Убедитесь, что в flow есть:
   - Review Profile (REQUIRED) - пользователь видит свои данные
   - Create User If Unique (ALTERNATIVE) - автоматическое создание пользователя

## Шаг 6: Тестирование интеграции

### 6.1. Откройте приложение
1. Перейдите на http://127.0.0.1:3000
2. Нажмите на кнопку Login
3. На странице Keycloak должна появиться кнопка "Яндекс ID"

### 6.2. Войдите через Яндекс:
1. Нажмите "Яндекс ID"
2. Вы будете перенаправлены на страницу авторизации Яндекса
3. Войдите с вашим Яндекс аккаунтом
4. Дайте согласие на использование данных (если включен consent)
5. Вы будете перенаправлены обратно в приложение

### 6.3. Проверьте созданного пользователя:
1. В Keycloak Admin Console перейдите в "Users"
2. Найдите нового пользователя (имя будет из Яндекс профиля)
3. Проверьте, что данные корректно синхронизированы

## Шаг 7: Сохранение данных пользователя в базу

Для сохранения профилей пользователей из Яндекса в вашу БД, добавьте обработчик в `bionicpro-auth` сервис:

```python
# В app.py добавьте endpoint для сохранения профиля

@app.route('/auth/save-yandex-profile', methods=['POST'])
@require_session
def save_yandex_profile():
    """Сохранение профиля пользователя из Яндекса в БД"""
    user_info = request.session_data.get('user_info', {})

    # Проверяем, что пользователь залогинен через Яндекс
    identity_provider = user_info.get('identity_provider')
    if identity_provider != 'yandex':
        return jsonify({'error': 'Not a Yandex user'}), 400

    # Сохраняем данные в БД
    # (требуется настройка подключения к PostgreSQL)

    return jsonify({'message': 'Profile saved'}), 200
```

## Troubleshooting

### Ошибка "Invalid redirect_uri":
- Проверьте, что в Яндекс OAuth правильно указан Redirect URI
- URL должен точно совпадать: `http://127.0.0.1:8080/realms/reports-realm/broker/yandex/endpoint`

### Пользователь не создается:
- Проверьте логи Keycloak
- Убедитесь, что "First Login Flow" правильно настроен
- Проверьте mappers для корректного маппинга данных

### Не приходят email данные:
- Убедитесь, что в Яндекс OAuth включен scope `login:email`
- Проверьте, что mapper для email правильно настроен
- В Яндекс аккаунте должен быть подтвержденный email

### Ошибка при получении токена:
- Проверьте Client ID и Client Secret
- Убедитесь, что Token URL правильный
- Проверьте, что приложение активно в Яндекс OAuth

## Дополнительные настройки безопасности

### 1. Привязка ролей для Яндекс пользователей:
1. "Identity Providers" → "yandex" → "Mappers"
2. Создайте Hardcoded Role mapper:
   - Name: default-role
   - Mapper Type: Hardcoded Role
   - Role: prothetic_user

### 2. Ограничение доменов email (опционально):
Можно настроить, чтобы принимались только email определенных доменов.

### 3. Логирование входов через Яндекс:
1. "Realm Settings" → "Events"
2. Включите "Login" и "Identity Provider Login" события
3. Настройте Event Listeners для мониторинга

## Полезные ссылки

- [Документация Yandex OAuth](https://yandex.ru/dev/id/doc/ru/)
- [Keycloak Identity Brokering](https://www.keycloak.org/docs/latest/server_admin/#_identity_broker)
- [OpenID Connect спецификация](https://openid.net/specs/openid-connect-core-1_0.html)
