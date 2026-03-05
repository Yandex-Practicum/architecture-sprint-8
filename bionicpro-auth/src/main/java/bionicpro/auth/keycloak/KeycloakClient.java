package bionicpro.auth.keycloak;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Map;
import java.util.Base64;
import java.util.stream.Collectors;

/**
 * HTTP-клиент для Keycloak OIDC endpoints.
 *
 * Использует java.net.http.HttpClient (JDK, ноль зависимостей).
 */
public class KeycloakClient {

    private static final Logger log = LoggerFactory.getLogger(KeycloakClient.class);
    private static final ObjectMapper json = new ObjectMapper();

    private final String tokenUrl;
    private final String authUrl;
    private final String logoutUrl;
    private final String clientId;
    private final String clientSecret;
    private final HttpClient httpClient;

    public KeycloakClient(String keycloakUrl, String keycloakExternalUrl, String realm, String clientId, String clientSecret) {
        var realmBase = keycloakUrl + "/realms/" + realm + "/protocol/openid-connect";
        var realmBaseExternal = keycloakExternalUrl + "/realms/" + realm + "/protocol/openid-connect";
        this.tokenUrl = realmBase + "/token";           // server-to-server
        this.authUrl = realmBaseExternal + "/auth";      // browser redirect
        this.logoutUrl = realmBaseExternal + "/logout";  // browser redirect
        this.clientId = clientId;
        this.clientSecret = clientSecret;
        this.httpClient = HttpClient.newHttpClient();
    }

    /** URL для Authorization Endpoint (для редиректа пользователя). */
    public String getAuthUrl() {
        return authUrl;
    }

    /** URL для Logout Endpoint. */
    public String getLogoutUrl() {
        return logoutUrl;
    }

    /**
     * Обменивает authorization code + code_verifier на токены.
     * POST /token с grant_type=authorization_code.
     */
    public TokenResponse exchangeCode(String code, String codeVerifier, String redirectUri) {
        var params = Map.of(
                "grant_type", "authorization_code",
                "code", code,
                "code_verifier", codeVerifier,
                "client_id", clientId,
                "client_secret", clientSecret,
                "redirect_uri", redirectUri
        );

        log.debug("Exchanging code for tokens (redirect_uri: {})", redirectUri);
        return postToken(params);
    }

    /**
     * Обновляет access_token через refresh_token.
     * POST /token с grant_type=refresh_token.
     */
    public TokenResponse refresh(String refreshToken) {
        var params = Map.of(
                "grant_type", "refresh_token",
                "refresh_token", refreshToken,
                "client_id", clientId,
                "client_secret", clientSecret
        );

        log.debug("Refreshing access token");
        return postToken(params);
    }

    // === Private ===

    private TokenResponse postToken(Map<String, String> params) {
        var body = params.entrySet().stream()
                .map(e -> URLEncoder.encode(e.getKey(), StandardCharsets.UTF_8) + "="
                        + URLEncoder.encode(e.getValue(), StandardCharsets.UTF_8))
                .collect(Collectors.joining("&"));

        var request = HttpRequest.newBuilder()
                .uri(URI.create(tokenUrl))
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();

        try {
            var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() != 200) {
                log.error("Keycloak token error: {} — {}", response.statusCode(), response.body());
                return null;
            }

            var node = json.readTree(response.body());
            var accessToken = node.get("access_token").asText();
            var refreshToken = node.has("refresh_token") ? node.get("refresh_token").asText() : null;
            var idToken = node.has("id_token") ? node.get("id_token").asText() : null;
            var expiresIn = node.get("expires_in").asLong();

            // Парсим id_token (JWT) для получения user info
            var userInfo = parseIdToken(idToken != null ? idToken : accessToken);

            return new TokenResponse(
                    accessToken, refreshToken, idToken,
                    Instant.now().getEpochSecond() + expiresIn,
                    userInfo
            );

        } catch (Exception e) {
            log.error("Keycloak request failed: {}", e.getMessage(), e);
            return null;
        }
    }

    /**
     * Парсит JWT (id_token или access_token) для извлечения user info.
     * JWT = header.payload.signature — нас интересует payload (Base64URL).
     * Мы НЕ валидируем подпись здесь — это делает downstream API.
     */
    private UserInfo parseIdToken(String jwt) {
        try {
            var parts = jwt.split("\\.");
            if (parts.length < 2) return UserInfo.UNKNOWN;

            var payload = new String(Base64.getUrlDecoder().decode(parts[1]), StandardCharsets.UTF_8);
            var node = json.readTree(payload);

            var sub = node.has("sub") ? node.get("sub").asText() : "unknown";
            var username = node.has("preferred_username") ? node.get("preferred_username").asText() : sub;
            var email = node.has("email") ? node.get("email").asText() : "";

            // Роли из realm_access.roles
            var roles = "";
            if (node.has("realm_access") && node.get("realm_access").has("roles")) {
                var rolesNode = node.get("realm_access").get("roles");
                var sb = new StringBuilder();
                for (var role : rolesNode) {
                    if (!sb.isEmpty()) sb.append(",");
                    sb.append(role.asText());
                }
                roles = sb.toString();
            }

            return new UserInfo(sub, username, email, roles);
        } catch (Exception e) {
            log.warn("Failed to parse JWT: {}", e.getMessage());
            return UserInfo.UNKNOWN;
        }
    }

    /** Результат обмена/обновления токенов. */
    public record TokenResponse(
            String accessToken,
            String refreshToken,
            String idToken,
            long accessTokenExpiresAt,  // unix timestamp (seconds)
            UserInfo userInfo
    ) {}

    /** Информация о пользователе из JWT. */
    public record UserInfo(String sub, String username, String email, String roles) {
        static final UserInfo UNKNOWN = new UserInfo("unknown", "unknown", "", "");
    }
}
