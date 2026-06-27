export const config = {
  port: Number(process.env.PORT || 8000),
  corsOrigin: process.env.CORS_ORIGIN || 'http://localhost:3000',
  keycloakIssuer:
    process.env.KEYCLOAK_ISSUER || 'http://localhost:8080/realms/reports-realm',
  keycloakJwksUri:
    process.env.KEYCLOAK_JWKS_URI ||
    'http://localhost:8080/realms/reports-realm/protocol/openid-connect/certs',
  reportUserIdClaim: process.env.REPORT_USER_ID_CLAIM || 'preferred_username',
  clickhouse: {
    url: process.env.CLICKHOUSE_URL || 'http://localhost:8123',
    username: process.env.CLICKHOUSE_USER || 'default',
    password: process.env.CLICKHOUSE_PASSWORD || '',
    database: process.env.CLICKHOUSE_DATABASE || 'bionicpro',
  },
};
