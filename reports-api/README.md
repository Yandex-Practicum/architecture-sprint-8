# reports-api

Reports service for BionicPRO (Go, standard library only). Serves each
authenticated user their own prosthesis report by reading the pre-aggregated
mart from ClickHouse — no heavy computation at request time.

## Endpoint

`GET /reports?from=YYYY-MM-DD&to=YYYY-MM-DD`

- **Authentication**: a valid Keycloak RS256 access token is required (verified
  against the realm JWKS). Missing/invalid → `401`.
- **Authorization**: the token must carry the `prothetic_user` realm role → else
  `403`.
- **Self-only**: the report is always for the token's `preferred_username`. A
  `user` query parameter that differs from the caller → `403`.
- **Watermark**: only data already loaded by the ETL is returned;
  `latest_processed_date` reports the boundary and a request beyond it returns a
  `notice`.

Response: client info + per-day telemetry metrics + a summary.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `LISTEN_ADDR` | `:8081` | |
| `KC_ISSUER` | `http://localhost:8080/realms/reports-realm` | validated against the `iss` claim |
| `KC_JWKS_URL` | `.../protocol/openid-connect/certs` | server-to-server JWKS |
| `CLICKHOUSE_URL` | `http://localhost:8123` | HTTP interface |
| `CLICKHOUSE_DB` / `CLICKHOUSE_TABLE` | `reports` / `user_report_mart` | |
| `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` | `default` / *(empty)* | |
| `REQUIRED_ROLE` | `prothetic_user` | set empty to allow any authenticated user |

## Run

```bash
go test ./...
go run .
```
