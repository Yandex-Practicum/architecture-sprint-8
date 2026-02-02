# Architecture BionicPro

## Запуск

1. Убедитесь, что запущен Docker (Docker Desktop или демон Docker).
2. В корне проекта выполните:

```bash
docker-compose up -d --build
```

3. Дождитесь старта сервисов (1–2 минуты). Доступны:
   - **Frontend**: http://localhost:3000
   - **Keycloak**: http://localhost:8080 (admin / admin)

## Ручная проверка (инструкция)

### Предварительные условия

- Сервисы запущены: `docker-compose up -d --build`, прошло 1–2 минуты.
- Браузер: Chrome, Firefox, Edge или аналог с DevTools.

### Тестовые пользователи Keycloak (realm reports-realm)

| Логин     | Пароль     | Роль        |
|-----------|------------|-------------|
| user1     | password123| user        |
| user2     | password123| user        |
| admin1    | admin123   | administrator |
| prothetic1| prothetic123 | prothetic_user |

---

### Шаг 1. Открыть приложение и включить DevTools

1. Откройте в браузере: **http://localhost:3000**
2. Должна отобразиться кнопка **Login** (если вы не авторизованы).
3. Откройте инструменты разработчика: **F12** или **Cmd+Option+I** (Mac) / **Ctrl+Shift+I** (Windows, Linux).
4. Перейдите на вкладку **Network** (Сеть).
5. Включите **Preserve log** (Сохранять журнал), чтобы запросы не пропадали при редиректах.

---

### Шаг 2. Проверить запрос авторизации (PKCE: code_challenge)

1. Нажмите кнопку **Login** на странице.
2. Должен произойти переход на страницу входа Keycloak (форма с полями Username и Password).
3. В списке запросов во вкладке Network найдите запрос, в URL которого есть:
   - `realms/reports-realm/protocol/openid-connect/auth`
   - Или в колонке **Name** — что-то вроде `auth?client_id=reports-frontend...`
4. Кликните по этому запросу и откройте панель справа.
5. Перейдите в **Headers** → **Request URL** (или **Query String Parameters**).
6. Убедитесь, что в URL присутствуют:
   - **`code_challenge`** — длинная строка (например, 43 символа в base64url).
   - **`code_challenge_method=S256`**

Если оба параметра есть — фронтенд отправляет авторизационный запрос с PKCE (S256).

---

### Шаг 3. Выполнить вход и проверить запрос токена (PKCE: code_verifier)

1. На странице Keycloak введите логин и пароль (например, **user1** / **password123**) и нажмите **Sign In**.
2. После успешного входа произойдёт возврат на **http://localhost:3000** — должна отобразиться страница «Usage Reports» с кнопкой **Download Report**.
3. Во вкладке Network найдите запрос к эндпоинту токена:
   - В URL или в **Name** должно быть: `openid-connect/token`
   - Метод: **POST**
4. Откройте этот запрос → вкладка **Payload** (или **Request** / **Form Data**).
5. Убедитесь:
   - Есть параметр **`code_verifier`** — длинная строка.
   - Параметра **`client_secret`** нет (публичный клиент с PKCE).

Если `code_verifier` присутствует и `client_secret` отсутствует — обмен кода на токен идёт по PKCE.

---

### Шаг 4. Итог проверки

- **Запрос к `/auth`**: в URL есть `code_challenge` и `code_challenge_method=S256`.
- **Запрос к `/token`**: в теле есть `code_verifier`, нет `client_secret`.

При выполнении обоих условий PKCE настроен корректно и проверка пройдена.
