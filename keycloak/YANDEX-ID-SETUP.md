# Identity Brokering: Яндекс ID (OAuth 2.0)

Аутентификация пользователей через внешний IdP **Яндекс ID** по OAuth 2.0. После входа сервис запрашивает согласие на использование данных и сохраняет профиль пользователя в БД.

## 1. Регистрация приложения в Яндекс OAuth

1. Перейдите в [Яндекс OAuth](https://oauth.yandex.com/) и войдите в аккаунт разработчика.
2. Создайте новое приложение: **Создать приложение** → укажите название (например, BionicPRO Reports).
3. Платформа: **Веб-сервисы**.
4. **Redirect URI** (Callback URL) укажите в формате, который использует Keycloak при Identity Brokering:
   - Для Keycloak на `http://localhost:8080`:
   - `http://localhost:8080/realms/reports-realm/broker/yandex/endpoint`
   - В продакшене замените на ваш домен Keycloak.
5. В блоке **Права доступа** (API Yandex ID) включите минимум:
   - **Доступ к логину, имени, фамилии, полу** (login:info — профиль)
   - **Доступ к email** (login:email)
   - При необходимости: аватар, дата рождения, телефон.
6. Сохраните приложение и запишите **ID приложения** (Client ID) и **Пароль** (Client Secret).

## 2. Добавление IdP в Keycloak

Keycloak не имеет встроенного провайдера «Yandex», поэтому используется **OpenID Connect v1.0** с ручным указанием URL Яндекса.

1. Откройте **http://localhost:8080** → **admin** / **admin** → realm **reports-realm**.
2. **Identity providers** → **Add provider** → выберите **OpenID Connect v1.0**.
3. Заполните:
   - **Alias (ID)** (обязательно): `yandex` — по этому значению в токене будет `identity_provider: "yandex"`.
   - **Display name**: `Яндекс ID`.
   - **First login flow**: оставьте **first broker login** (или выберите кастомный с экраном согласия).
   - **Authorization URL**: `https://oauth.yandex.com/authorize`
   - **Token URL**: `https://oauth.yandex.com/token`
   - **Logout URL**: оставьте пустым.
   - **User Info URL**: `https://login.yandex.ru/info`
   - **Client ID**: ID приложения из п. 1.
   - **Client Secret**: пароль приложения из п. 1.
   - **Default Scopes**: `login:info login:email` (при необходимости добавьте `login:avatar` и др.).
4. **Advanced** (если есть):
   - Для User Info API Яндекса ожидает заголовок `Authorization: OAuth <token>`, а не `Bearer`. Если Keycloak отправляет только `Bearer`, пользовательские поля могут не подтянуться; в таком случае данные профиля будут браться из токена доступа или потребуется кастомный IdP/расширение. Для типовой сборки оставьте настройки по умолчанию.
5. **Save**.

## 3. Маппинг атрибутов (Mappers)

В созданном провайдере **yandex** откройте **Mappers** и проверьте/добавьте маппинги, чтобы в пользователе Keycloak и в токене были поля из Яндекса:

| Name        | Mapper Type        | Claim / Attribute     | User Attribute    |
|-------------|--------------------|------------------------|-------------------|
| email       | Attribute Importer  | default_email / email  | email             |
| first name  | Attribute Importer  | first_name             | firstName         |
| last name   | Attribute Importer  | last_name              | lastName          |
| username    | Attribute Importer  | login                  | username          |
| yandex id   | Attribute Importer  | id                     | (например, атрибут yandex_id) |

Точные имена полей в ответе Яндекса: [API Yandex ID — user information](https://yandex.com/dev/id/doc/en/user-information). Если User Info в Keycloak не срабатывает из‑за формата заголовка, данные могут приходить из настроек токена/IdP token.

## 4. Согласие пользователя (Consent)

Чтобы после аутентификации сервис запрашивал разрешение на использование данных:

1. **Clients** → выберите клиент **bionicpro-auth**.
2. Включите **Consent Required** (Consent screen).
3. **Save**.

После первого входа (в т.ч. через Яндекс) пользователь увидит экран согласия Keycloak на передачу данных приложению. При необходимости настройте текст и обязательные/опциональные scopes в **Client scopes** и **Client scope mappings**.

## 5. Вход через Яндекс ID

1. Пользователь открывает приложение и нажимает вход (например, **http://localhost:3000** или **http://localhost:8000/auth/login**).
2. Редирект на Keycloak → на странице входа должна быть кнопка **Яндекс ID** (или отображаемое имя провайдера).
3. После выбора «Яндекс ID» — редирект на Яндекс, пользователь разрешает доступ.
4. Keycloak создаёт/обновляет пользователя в realm и при включённом **Consent Required** показывает экран согласия.
5. После подтверждения — редирект обратно в приложение (callback bionicpro-auth). Сервис bionicpro-auth по полю `identity_provider` в токене определяет вход через Яндекс и сохраняет профиль в БД.

## 6. Сохранение профиля в БД

Сервис **bionicpro-auth** при успешном callback проверяет в JWT от Keycloak claim `identity_provider`. Если он равен `yandex`, данные профиля (sub, email, имя, фамилия и т.д.) сохраняются в таблицу `user_profiles`. Подробности — в коде и конфигурации БД bionicpro-auth.

## Ссылки

- [OAuth 2.0 в Яндекс ID](https://yandex.com/dev/id/doc/en/concepts/ya-oauth-intro)
- [Получение кода и обмен на токен](https://yandex.com/dev/id/doc/en/codes/code-url)
- [Данные пользователя (login.yandex.ru/info)](https://yandex.com/dev/id/doc/en/user-information)
- [Регистрация приложения](https://yandex.com/dev/id/doc/en/register-client)
