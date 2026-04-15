# Экспорт Keycloak Realm Configuration

После завершения всех настроек в Keycloak (PKCE, MFA, LDAP, Яндекс ID), необходимо экспортировать финальную конфигурацию.

## Способ 1: Экспорт через Admin Console (рекомендуется для разработки)

### Шаги:
1. Войдите в Keycloak Admin Console (http://127.0.0.1:8080)
2. Выберите realm "reports-realm"
3. В левом меню выберите "Realm Settings"
4. Перейдите во вкладку "Action" → "Partial export"
5. Настройте параметры экспорта:
   - ✅ Export groups and roles
   - ✅ Export clients
   - ✅ Export identity providers (для Яндекс ID)
   - ⚠️  Не включайте "Export users" в production (содержит пароли)
6. Нажмите "Export"
7. Сохраните файл как `keycloak-results-export.json` в папку `keycloak/`

## Способ 2: Экспорт через CLI (для production)

### Используя Docker:
```bash
docker exec -it bionicpro-keycloak /opt/keycloak/bin/kc.sh export \
  --dir /tmp/export \
  --realm reports-realm \
  --users skip
```

Затем скопируйте файл из контейнера:
```bash
docker cp bionicpro-keycloak:/tmp/export/reports-realm.json ./keycloak/keycloak-results-export.json
```

## Способ 3: Экспорт при старте контейнера

Добавьте в docker-compose.yaml для экспорта при старте:
```yaml
command:
  - start-dev
  - --import-realm
  - --export-realm
```

## Важные замечания

### Безопасность:
- **НЕ ЭКСПОРТИРУЙТЕ пользователей с паролями в production**
- Секреты клиентов должны быть заменены на переменные окружения
- LDAP credentials не должны быть в экспорте для публичных репозиториев

### Что должно быть в финальном экспорте:
- ✅ Realm settings (OTP policy, session timeouts)
- ✅ Roles (prothetic_user, administrator, user)
- ✅ Clients (bionicpro-auth, reports-frontend, reports-api)
- ✅ Client configurations (PKCE settings, access token lifespan)
- ✅ Authentication flows (с OTP)
- ✅ Identity Provider настройки (Яндекс ID)
- ✅ User Federation (LDAP configuration)

### Что НЕ должно быть:
- ❌ Пользователи с паролями
- ❌ Client secrets в открытом виде
- ❌ LDAP bind credentials

## Чистка чувствительных данных из экспорта

После экспорта вручную отредактируйте JSON:

```bash
# Замените client secrets на плейсхолдеры
sed -i 's/"secret": ".*"/"secret": "${CLIENT_SECRET}"/g' keycloak-results-export.json

# Удалите LDAP credentials
# Отредактируйте вручную секцию "components" → "org.keycloak.storage.UserStorageProvider"
```

## Проверка экспорта

Убедитесь, что экспортированный файл содержит:

```bash
# Проверка наличия ключевых настроек
grep -q '"pkce.code.challenge.method"' keycloak-results-export.json && echo "✓ PKCE enabled"
grep -q '"otpPolicyType"' keycloak-results-export.json && echo "✓ OTP configured"
grep -q '"yandex"' keycloak-results-export.json && echo "✓ Yandex ID configured"
grep -q '"ldap"' keycloak-results-export.json && echo "✓ LDAP configured"
```

## Тестирование импорта

Протестируйте экспорт на чистом Keycloak:

```bash
# Остановите текущие контейнеры
docker-compose down -v

# Замените realm-export.json на keycloak-results-export.json в docker-compose.yaml
# Запустите заново
docker-compose up -d

# Проверьте, что все настройки применились
```

## Финальное расположение файла

Экспортированный файл должен быть сохранен как:
```
/Users/nspeganov/IdeaProjects/architecture-bionicpro/keycloak/keycloak-results-export.json
```

И должен быть указан в docker-compose.yaml:
```yaml
volumes:
  - ./keycloak/keycloak-results-export.json:/opt/keycloak/data/import/keycloak-results-export.json
