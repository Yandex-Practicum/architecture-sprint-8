Получить токен
curl --location 'http://localhost:8080/realms/reports-realm/protocol/openid-connect/token' \
--header 'Content-Type: application/x-www-form-urlencoded' \
--header 'X-API-Key: {{token}}' \
--data-urlencode 'client_id=reports-frontend' \
--data-urlencode 'grant_type=password' \
--data-urlencode 'username=prothetic3' \
--data-urlencode 'password=prothetic123'

проверка АПИ
curl --location 'localhost:8000/reports' \
--header 'Authorization: Bearer ***'

проверка валидности токена

curl --location 'http://localhost:8080/realms/reports-realm/protocol/openid-connect/token/introspect' \
--header 'Content-Type: application/x-www-form-urlencoded' \
--header 'X-API-Key: {{token}}' \
--data-urlencode 'client_id=reports-api' \
--data-urlencode 'client_secret=IiePgosFlLulH7K9A8WEY0bKHZkKzqYg' \
--data-urlencode 'token=***'