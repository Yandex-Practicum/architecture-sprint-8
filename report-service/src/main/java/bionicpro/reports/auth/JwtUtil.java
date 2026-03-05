package bionicpro.reports.auth;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.Base64;
import java.util.Map;

/**
 * Лёгкий парсер JWT-токена.
 * <p>
 * Декодирует payload (claims) из JWT без криптографической верификации подписи.
 * <p>
 * Почему это безопасно в нашей архитектуре:
 * <ul>
 *   <li>Report Service доступен только из внутренней docker-сети</li>
 *   <li>Запросы приходят от BFF (bionicpro-auth), который уже проверил
 *       сессию и владеет валидным access_token от Keycloak</li>
 *   <li>Прямой доступ из интернета к Report Service невозможен</li>
 * </ul>
 * <p>
 * В production-среде с несколькими точками входа стоит добавить
 * верификацию подписи через JWKS-эндпоинт Keycloak.
 */
public final class JwtUtil {

    private static final ObjectMapper mapper = new ObjectMapper();

    private JwtUtil() {}

    /**
     * Извлекает claims из JWT payload.
     * JWT формат: header.payload.signature (Base64URL-encoded).
     *
     * @param token JWT-строка (без префикса "Bearer ")
     * @return Map с claims (sub, preferred_username, email, realm_access, ...)
     * @throws IllegalArgumentException если токен имеет неверный формат
     */
    public static Map<String, Object> parseClaims(String token) {
        String[] parts = token.split("\\.");
        if (parts.length < 2) {
            throw new IllegalArgumentException("Invalid JWT format: expected at least 2 parts");
        }

        // Payload — вторая часть JWT
        byte[] payloadBytes = Base64.getUrlDecoder().decode(parts[1]);

        try {
            return mapper.readValue(payloadBytes, new TypeReference<>() {});
        } catch (Exception e) {
            throw new IllegalArgumentException("Failed to parse JWT payload: " + e.getMessage(), e);
        }
    }
}
