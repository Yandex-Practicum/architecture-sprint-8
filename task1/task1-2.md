# Изменения

**Keycloak** (`realm-export.json`): добавлен `pkce.code.challenge.method: "S256"`, отключен `directAccessGrantsEnabled`.

**Фронтенд** (`App.tsx`): добавлен `initOptions: { pkceMethod: 'S256' }`.

# Проверка

`http://localhost:8080/realms/reports-realm/protocol/openid-connect/auth?client_id=reports-frontend&redirect_uri=http%3A%2F%2Flocalhost%3A3000%2F&state=23127a12-50d6-4516-850f-539eecd25758&response_mode=fragment&response_type=code&scope=openid&nonce=47d4d4b5-b5de-43ec-8c50-b419007587eb&code_challenge=DvsUZHJCJwRSsIczvbsqjN9TdhuUtEWgf7qxMhsIA7E&code_challenge_method=S256`
Запрос `/auth` содержит `code_challenge` и `code_challenge_method=S256`.

`code=c9041487-e76f-4bba-8bcd-0e9e3e122fd7.508defac-1fb2-42ce-9ff9-15227ca0403c.54c4002d-d503-427d-909e-1240e7b4e45f&grant_type=authorization_code&client_id=reports-frontend&redirect_uri=http%3A%2F%2Flocalhost%3A3000%2F&code_verifier=RRMX9OudIeYWPbrxRcGxRBmUkUU0Ei2rgM9xlzNdhvuqvbD8dAWYPqEBxdFE8p3EoemRd9TPei16mB6BaPdEgH6YLiV1wak6`
Запрос `/token` содержит `code_verifier`. Токены получены успешно.
