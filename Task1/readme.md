


Keycloak -  http://localhost:8080

reports-realm >> Clients >> Settings:

- Client authentication - OFF
- Standard flow - ON
- Implicit flow - OFF
- Direct access grants - OFF
- Valid redirect URIs - http://localhost:3000/*
- Web origins - http://localhost:3000

логин - http://localhost:3000/

---

task 1.3

Clients - Create client

Client type: OpenID Connect

Client ID: bionicpro-auth

Name: bionicpro-auth

Client authentication - ON

Valid redirect URIs - http://localhost:8001/auth/callback

Access Token Lifespan - 5 мин (по умолчанию)

---