# Инструкция по настройке LDAP User Federation в Keycloak

## Шаг 1: Войдите в Keycloak Admin Console
1. Откройте http://127.0.0.1:8080
2. Войдите с креденшалами: admin/admin
3. Выберите realm "reports-realm"

## Шаг 2: Добавьте LDAP User Federation Provider
1. В левом меню выберите "User Federation"
2. Нажмите "Add provider" → выберите "ldap"

## Шаг 3: Настройте подключение к LDAP
Заполните следующие поля:

### General Settings:
- **Console Display Name**: BionicPRO LDAP
- **Priority**: 0
- **Edit Mode**: WRITABLE
- **Sync Registrations**: ON
- **Import Users**: ON

### Connection Settings:
- **Connection URL**: ldap://openldap:389
- **Bind Type**: simple
- **Bind DN**: cn=admin,dc=bionicpro,dc=com
- **Bind Credential**: admin123

### LDAP Search Settings:
- **Users DN**: ou=people,dc=bionicpro,dc=com
- **Username LDAP attribute**: uid
- **RDN LDAP attribute**: uid
- **UUID LDAP attribute**: entryUUID
- **User Object Classes**: inetOrgPerson, organizationalPerson
- **Search Scope**: One Level

### Advanced Settings:
- **Enable StartTLS**: OFF
- **Use Truststore SPI**: Never
- **Connection Pooling**: ON
- **Pagination**: ON

## Шаг 4: Test Connection
1. Нажмите кнопку "Test connection"
2. Убедитесь, что соединение успешно
3. Нажмите "Test authentication"
4. Убедитесь, что аутентификация прошла успешно

## Шаг 5: Настройте Mappers для LDAP
После сохранения основной конфигурации, перейдите во вкладку "Mappers":

### Создайте mapper для групп:
1. Нажмите "Create"
2. Заполните:
   - **Name**: group-mapper
   - **Mapper Type**: group-ldap-mapper
   - **LDAP Groups DN**: ou=groups,dc=bionicpro,dc=com
   - **Group Name LDAP Attribute**: cn
   - **Group Object Classes**: groupOfNames
   - **Membership LDAP Attribute**: member
   - **Membership Attribute Type**: DN
   - **Mode**: READ_ONLY
   - **User Groups Retrieve Strategy**: LOAD_GROUPS_BY_MEMBER_ATTRIBUTE

### Mapper для email:
1. Name: email
2. Mapper Type: user-attribute-ldap-mapper
3. User Model Attribute: email
4. LDAP Attribute: mail
5. Read Only: OFF

### Mapper для first name:
1. Name: first name
2. Mapper Type: user-attribute-ldap-mapper
3. User Model Attribute: firstName
4. LDAP Attribute: givenName
5. Read Only: OFF

### Mapper для last name:
1. Name: last name
2. Mapper Type: user-attribute-ldap-mapper
3. User Model Attribute: lastName
4. LDAP Attribute: sn
5. Read Only: OFF

## Шаг 6: Синхронизируйте пользователей
1. Вернитесь в главную страницу LDAP провайдера
2. Нажмите "Synchronize all users"
3. Проверьте, что пользователи импортированы в "Users" → "View all users"

## Шаг 7: Настройте маппинг ролей
1. В меню "Roles" создайте соответствующие роли, если их нет
2. В User Federation → LDAP Provider → Mappers создайте mapper для ролей:
   - **Name**: role-mapper
   - **Mapper Type**: role-ldap-mapper
   - **LDAP Roles DN**: ou=groups,dc=bionicpro,dc=com
   - **Role Name LDAP Attribute**: cn
   - **Role Object Classes**: groupOfNames
   - **Membership LDAP Attribute**: member
   - **Mode**: READ_ONLY

## Шаг 8: Тестирование
1. Попробуйте войти с LDAP пользователем:
   - Username: ldap_user1
   - Password: ldapuser123

2. Проверьте, что пользователь успешно аутентифицируется
3. Убедитесь, что роли и атрибуты корректно маппятся

## Тестовые пользователи LDAP:
- **ldap_user1** / ldapuser123 (группа: prothetic_users)
- **ldap_user2** / ldapuser123 (группа: prothetic_users)
- **ldap_admin** / ldapadmin123 (группа: administrators)

## Troubleshooting:
Если возникают проблемы:
1. Проверьте логи Keycloak
2. Убедитесь, что OpenLDAP запущен: `docker-compose logs openldap`
3. Проверьте connectivity между контейнерами
4. Используйте LDAP browser (Apache Directory Studio) для проверки структуры LDAP
