# LDAP интеграция BionicPRO (uid, dc=example,dc=com)

## LDAP данные
- Bind DN: `cn=admin,dc=example,dc=com`, пароль: `admin`
- База пользователей: `ou=People,dc=example,dc=com`
- Пользователи (логин через `uid`):
	- john.doe / password
	- jane.smith / password
	- alex.johnson / password
- Группы (роль → участники):
	- user → jane.smith
	- prothetic_user → alex.johnson, john.doe