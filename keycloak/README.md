# Keycloak Configuration

## Files

- **realm-export.json**: Main realm configuration for `reports-realm`
- **configure-master-realm.sh**: Disables SSL requirement for local development
- **configure-yandex-idp.sh**: Applies Yandex ID User Profile Claims configuration

## Yandex ID Integration

The Yandex OAuth2 Identity Provider is automatically configured during container startup.

### User Profile Claims Mapping

Keycloak OAuth2 Identity Provider has **two sets of parameters**:
- `*Attribute` — for parsing JSON response from **UserInfo endpoint**
- `*Claim` — for the UI **"User profile claims"** section

Both must be configured for correct operation:

| Keycloak UI Field | Yandex API Field | Attribute Config | Claim Config |
|-------------------|------------------|------------------|--------------|
| ID Claim | `id` | `config.userIdAttribute` | `config.userIdClaim` |
| Username Claim | `login` | `config.userNameAttribute` | `config.userNameClaim` |
| Email Claim | `default_email` | `config.emailAttribute` | `config.emailClaim` |
| Name Claim | `name` | `config.nameAttribute` | `config.nameClaim` |
| Given name Claim | `first_name` | `config.givenNameAttribute` | `config.givenNameClaim` |
| Family name Claim | `last_name` | `config.familyNameAttribute` | `config.familyNameClaim` |

### Why the Init Script?

Keycloak's `--import-realm` flag doesn't always correctly apply Identity Provider User Profile Claims from realm-export.json. The `configure-yandex-idp.sh` script runs after import and explicitly sets these values via the Admin API.

### Manual Verification

To verify the configuration was applied:

1. Open Keycloak Admin Console: http://localhost:8080/admin/master/console/
2. Navigate to: reports-realm → Identity providers → Яндекс ID → Settings
3. Check the "User profile claims" section

### Troubleshooting

Check init container logs:
```bash
docker-compose logs keycloak-yandex-init
```

Expected output:
```
✓ Yandex ID User Profile Claims configured successfully!
  - ID Claim: id
  - Username Claim: login
  - Email Claim: default_email
  - Name Claim: name
  - Given name Claim: first_name
  - Family name Claim: last_name
```

If the init container fails, check that:
- Keycloak is fully started (check `docker-compose logs keycloak`)
- realm-export.json was imported correctly
- Yandex Identity Provider exists in reports-realm
