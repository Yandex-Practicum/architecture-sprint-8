package com.bionicpro.auth.oauth;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.Base64;
import java.util.Optional;

/**
 * Разбор claim'ов из JWT access token без проверки подписи (токен уже доверен после выдачи Keycloak).
 */
public final class AccessTokenClaims {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private AccessTokenClaims() {}

    /**
     * Извлекает claim {@code sub} из JWT access token. Для opaque-токенов возвращает {@link Optional#empty()}.
     */
    public static Optional<String> subFromAccessToken(String accessToken) {
        if (accessToken == null || accessToken.isBlank()) {
            return Optional.empty();
        }
        String[] parts = accessToken.split("\\.");
        if (parts.length < 2) {
            return Optional.empty();
        }
        try {
            byte[] json = base64UrlDecode(parts[1]);
            JsonNode node = MAPPER.readTree(json);
            JsonNode sub = node.get("sub");
            if (sub == null || !sub.isTextual()) {
                return Optional.empty();
            }
            return Optional.of(sub.asText());
        } catch (Exception e) {
            return Optional.empty();
        }
    }

    private static byte[] base64UrlDecode(String segment) {
        StringBuilder sb = new StringBuilder(segment);
        while (sb.length() % 4 != 0) {
            sb.append('=');
        }
        return Base64.getUrlDecoder().decode(sb.toString());
    }
}
