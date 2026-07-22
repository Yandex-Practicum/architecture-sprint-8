# Задание 1. Повышение безопасности системы

## Задача 1. Предложите архитектурное решение и доработайте диаграмму C4 для управления учётными данными пользователя. 

На [схему](https://github.com/tammaco/architecture-pro-bionicpro/Task1/BionicPRO_C4_model.drawio.xml) добавлен контейнер **bionicpro-auth**, который берёт будет явялться единой точкой входа всех клиентов.
В его состав входят:
- сервис bionicpro-auth-api, который берёт на себя взаимодействие с Keycloak.
Для РФ он будет развёрнут локально.
- сервис определения региона RegionRouter, который в зависимости от настроек будет обращаться к Keycloak в РФ или другой страны
- хранения токено предлагается осуществить с Redis

## Задача 2. Улучшите безопасность существующего приложения, заменив Code Grant на PKCE. 

Исправлен файл [realm-export.json](https://github.com/tammaco/architecture-pro-bionicpro/keycloak/realm-export.json), добавлены свойства:

1. Отключено свойство directAccessGrantsEnabled
```
"directAccessGrantsEnabled": false
```

2. Включен Standard Flow режим:
```
"standardFlowEnabled": true
```

3. Отключен Implicit Flow:
```
"implicitFlowEnabled": false
```

4. Добавлены атрибуты PKCE:
```
 "attributes": {
        "pkce.code.challenge.method": "S256",
        "oauth2.device.authorization.grant.enabled": false,
        "backchannel.logout.session.required": true,
        "backchannel.logout.revoke.offline.tokens": false
      },
```

Исправлен файл для фронтенда [App.tsx](https://github.com/tammaco/architecture-pro-bionicpro/frontend/src/App.tsx), добавлены свойства:

```
 initOptions={{
        pkceMethod: 'S256',
        checkLoginIframe: false,
      }}
```

## Задача 3. Обеспечьте безопасное получение и хранение access-и refresh-токенов.

Добавлен сервис **bionicpro-auth**.
В нём реализовано безопасное получение и хранение access-и refresh-токенов, а также ротация сессии в рамках действующего access_token.

## Задача 4. Добавьте LDAP для возможности получения данных о пользователях представительства BionicPRO в другой стране.

1. Добавить раздел сервиса openldap в docker-compose:

```
openldap:
    image: osixia/openldap:1.5.0
    container_name: bionicpro-ldap
    ports:
      - "389:389"
    environment:
      LDAP_ORGANISATION: "Example Company"
      LDAP_DOMAIN: "example.com"
      LDAP_ADMIN_PASSWORD: "admin123"
      LDAP_TLS: "false"
    volumes:
      - ./ldap/config.ldif:/container/service/slapd/assets/config/bootstrap/ldif/custom/01-bootstrap.ldif
    networks:
      - bionic-network
    restart: unless-stopped
```

и поднять все контенеры заново:

```
docker compose down

docker compose up -d
```

2. Открыть админ-панель: http://localhost:8080/admin/ и выбрать reports-realm

Вкладка **User federation**->**Add Ldap providers**
Настройки провайдера:

|Поле|Значение|
|-|-|
|Connection URL|ldap://openldap:389|
|Users DN|ou=People,dc=example,dc=com|
|Bind DN|cn=admin,dc=example,dc=com|
|Bind Credential|admin123|
|Edit mode|READ_ONLY|
|Users DN|ou=People,dc=example,dc=com|
|Username LDAP attribute|uid|
|RDN LDAP attribute|uid|
|UUID LDAP attribute|entryUUID|
|User object classes|inetOrgPerson, organizationalPerson, person|

3. Маппинг ролей

Вкладка **Mappers**->**Add mapper**

**Mapper type** -> **group-ldap-mapper**

Настройки маппинга:

|Поле|Значение|
|-|-|
|Name|Groups Mapper|
|Groups DN|ou=Groups,dc=example,dc=com|
|Group Name LDAP Attribute|cn|
|Group Object Classes|groupOfNames|
|Member Attribute|member|
|Member Attribute Type|DN|
|Mode|LDAP_ONLY|

4. Синхронизация

User Federation -> Synchronize all users

## Задача 5. Настройте MFA

1. Настройте в Keycloak механизм OTP-аутентификации

Открыть админ-панель: http://localhost:8080/admin/ и выбрать reports-realm.
Вкладка **Authentication**->**Required Actions**->**Configure OTP**: Set as default action = On

2. Для пользователей настроить:

Details -> Required User Actions -> Add action  -> Configure OTP

3. Скачать Free OTP и проверить вход.

![Результат](https://github.com/tammaco/architecture-pro-bionicpro/Task1/screenshots/MFA.png)

## Задача 6. Добавьте OAuth 2.0 от Яндекс ID

1. Создать приложение для аутентификации на https://oauth.yandex.ru/

Redirect URI http://localhost:8080/realms/reports-realm/broker/yandex/endpoint
После создания получены Client ID и Client secret.

Интеграция с Яндексом невозможна стандартными средствами Keycloak, поэтому добавлены 2 эндпоинта в bionicpro-auth и кнопка для входа во frontend.

![Результат1](https://github.com/tammaco/architecture-pro-bionicpro/Task1/screenshots/yandex_вход.png)
![Результат2](https://github.com/tammaco/architecture-pro-bionicpro/Task1/screenshots/yandex_passport.png)





