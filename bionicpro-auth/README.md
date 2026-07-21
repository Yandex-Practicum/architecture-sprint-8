# bionicpro-auth

Backend-for-Frontend (BFF) authentication service for BionicPRO, written in Go
(standard library only, no external dependencies).

It moves all OAuth2/OIDC token handling out of the SPA. The browser only ever
receives an opaque, `HttpOnly` + `Secure` session cookie; the access and refresh
tokens obtained from Keycloak stay on the server, bound to the session,
refreshed automatically and rotated on every request.

## Why a BFF

- **Tokens never reach the frontend** — closes the SSO leak that let attackers
  exfiltrate user data.
- **`access_token` lifetime ≤ 2 min** — a stolen access token is useless almost
  immediately; the BFF silently refreshes it server-side using the refresh token.
- **Session rotation** — every authenticated request re-binds the tokens to a
  brand-new session id (defence against session fixation).

## Endpoints

| Method & path        | Auth | Purpose                                                                 |
|----------------------|------|-------------------------------------------------------------------------|
| `GET /healthz`       | no   | Liveness probe.                                                         |
| `GET /auth/login`    | no   | Starts Authorization Code + PKCE (S256); 302 to Keycloak.              |
| `GET /auth/callback` | no   | Exchanges code+verifier for tokens, creates the session, sets cookie.  |
| `GET /auth/me`       | yes  | Returns the current user (username, email, roles).                     |
| `POST /auth/logout`  | —    | Revokes the refresh token at Keycloak, drops the session and cookie.   |
| `GET /api/reports`   | yes  | Protected resource (demo payload, or proxied to `DOWNSTREAM_API_URL`). |
| `GET /api/*`         | yes  | Authenticated reverse proxy to the downstream API.                     |

Every `yes` endpoint runs through the session middleware, which:
1. reads the session cookie and looks up the server-side session;
2. refreshes the access token via the refresh token if it is about to expire;
3. **rotates the session id**, sets the new cookie and returns it in `X-Session-Id`.

## Configuration (environment variables)

| Variable            | Default                                | Notes                                             |
|---------------------|----------------------------------------|---------------------------------------------------|
| `LISTEN_ADDR`       | `:8000`                                |                                                   |
| `KC_EXTERNAL_URL`   | `http://localhost:8080`                | Browser-facing Keycloak URL (authorize + issuer). |
| `KC_INTERNAL_URL`   | `http://localhost:8080`                | Server-to-server URL (token/refresh/logout).      |
| `KC_REALM`          | `reports-realm`                        |                                                   |
| `KC_CLIENT_ID`      | `bionicpro-auth`                       | Confidential client.                              |
| `KC_CLIENT_SECRET`  | `bionicpro-auth-secret`                |                                                   |
| `REDIRECT_URI`      | `http://localhost:8000/auth/callback`  | Must match the Keycloak client redirect URI.      |
| `FRONTEND_URL`      | `http://localhost:3000`                | CORS origin + post-login redirect.                |
| `COOKIE_SECURE`     | `true`                                 | Set `false` only for local plain-http testing.    |
| `SESSION_TTL`       | `30m`                                  | Must be greater than the access-token lifetime.   |
| `ACCESS_SKEW`       | `10s`                                  | Refresh this long before the access token expires.|
| `DOWNSTREAM_API_URL`| *(empty)*                              | Optional reports backend to proxy `/api/*` to.    |

## Run

```bash
# locally against a Keycloak on :8080
COOKIE_SECURE=false go run .

# tests
go test ./...
```

Or via the repository `docker-compose.yaml` (`docker compose up --build`).
