# Keycloak realm files

- `realm-export.json` — the baseline `reports-realm` bootstrap that `docker-compose.yaml`
  imports on a fresh `keycloak` container (`--import-realm`). Left untouched so a clean
  `docker compose up` always starts from the same known state.
- `keycloak-results-export.json` — a snapshot of the realm **after** applying Задание 1's
  security changes: PKCE on `reports-frontend` (redirect URI repointed at
  `bionicpro-auth`'s callback), OpenLDAP user federation + LDAP-group-to-realm-role
  mapping, mandatory OTP (`CONFIGURE_TOTP` forced as a default required action), and the
  Yandex ID identity provider. This is the deliverable the assignment asks for; it is
  not auto-imported by `docker-compose.yaml`.
- `configure-realm.sh` — the exact `kcadm.sh` script used to produce that snapshot.
  Reproduce it against a freshly started stack:

  ```bash
  docker compose up -d keycloak_db keycloak openldap redis
  YANDEX_CLIENT_ID=... YANDEX_CLIENT_SECRET=... ./keycloak/configure-realm.sh
  ```

  Without real `YANDEX_CLIENT_ID`/`YANDEX_CLIENT_SECRET` (register an app at
  https://oauth.yandex.ru), the script writes placeholder values and the Yandex ID
  login button will be present but non-functional until you swap them in via the Admin
  Console (Identity Providers → yandex) or by re-running the relevant `kcadm.sh update`
  call.

## Known LDAP data fix

`ldap/config.ldif`'s `alex` entry originally had `dn: uid=alex,...` while its `uid`
attribute (and the `prothetic_user` group's `member` reference) said
`uid=alex.johnson,...` — a DN mismatch that silently broke his LDAP-group-to-role sync
(John Doe and Jane Smith, whose DN already matched their `uid`, were unaffected). Fixed
by renaming the DN to `uid=alex.johnson,...` to match.
