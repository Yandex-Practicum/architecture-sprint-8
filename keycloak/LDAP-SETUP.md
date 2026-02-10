# Настройка Keycloak для работы с LDAP (Задача 4)

После запуска `docker compose up -d` OpenLDAP уже развёрнут и заполнен пользователями из `ldap/config.ldif`.  
Настройку Keycloak для авторизации через LDAP нужно выполнить вручную в Admin Console.

## 1. Подключение LDAP User Federation

1. Откройте **http://localhost:8080** → войдите как **admin** / **admin**.
2. Выберите realm **reports-realm**.
3. Меню **User federation** → **Add provider** → выберите **ldap**.
4. Заполните:
   - **Vendor**: Other
   - **Connection URL**: `ldap://openldap:389` (из хоста Docker; с хоста машины: `ldap://localhost:389`)
   - **Bind DN**: `cn=admin,dc=example,dc=com`
   - **Bind Credential**: `admin`
   - Нажмите **Test connection** (из контейнера Keycloak хост будет `openldap`).
5. Нажмите **Save**.
6. В настройках провайдера LDAP:
   - **Edit mode**: READ_ONLY (пользователи только из LDAP).
   - **Sync registrations**: OFF.
   - **Username LDAP attribute**: `uid`
   - **RDN LDAP attribute**: `uid`
   - **UUID LDAP attribute**: `entryUUID`
   - **User Object Classes**: `inetOrgPerson, organizationalPerson`
   - **Users DN**: `ou=People,dc=example,dc=com`
   - При необходимости настройте маппинг **first name**, **last name**, **email** (например, атрибуты `cn`, `sn`, `mail`).

## 2. Маппинг ролей (LDAP Groups → Keycloak Realm Roles)

Чтобы роли из LDAP (группы `user`, `prothetic_user`) превращались в роли Keycloak и были едиными для разных представительств:

1. В том же провайдере LDAP откройте вкладку **Mappers**.
2. **Create** → выберите тип **group-ldap-mapper**.
3. Создайте маппинг:
   - **Name**: `ldap-groups-to-roles`
   - **LDAP Groups DN**: `ou=Groups,dc=example,dc=com`
   - **Group Name LDAP Attribute**: `cn`
   - **Realm Role Mapping**: включить (или указать префикс, если нужно).
   - **Mode**: LDAP groups → realm roles (чтение групп из LDAP и сопоставление с realm roles с теми же именами).

4. Убедитесь, что в realm уже есть роли с именами **user** и **prothetic_user** (они заданы в `realm-export.json`).  
   Имена групп в LDAP (`cn=user`, `cn=prothetic_user`) должны совпадать с именами realm roles в Keycloak.

При таком маппинге пользователи из LDAP (например, **john.doe**, **jane.smith**, **alex.johnson**) при входе получают роли Keycloak в соответствии с членством в LDAP-группах.

## 3. Синхронизация пользователей из LDAP

1. В **User federation** → выберите провайдер **ldap**.
2. Вкладка **Synchronization** → **Sync all users** (при необходимости — **Sync changed users**).

После этого пользователи из LDAP появятся в Keycloak и смогут входить с паролями из LDAP (например, **john.doe** / **password**, **jane.smith** / **password**, **alex.johnson** / **password**).

## 4. Пользователи и группы в LDAP (из config.ldif)

| Пользователь   | Пароль   | Группа (роль)   |
|----------------|----------|-----------------|
| john.doe       | password | prothetic_user  |
| jane.smith     | password | user            |
| alex.johnson   | password | prothetic_user  |

Роли **user** и **prothetic_user** в Keycloak совпадают с именами групп в LDAP для единого маппинга между представительствами.
