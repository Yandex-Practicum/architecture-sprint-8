package com.bionicpro.auth.oauth;

import com.bionicpro.auth.crypto.TokenEncryption;
import com.bionicpro.auth.session.SessionTokens;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.time.Instant;

@Service
public class KeycloakTokenRefreshService {

    private final RestClient restClient = RestClient.builder().build();
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final TokenEncryption tokenEncryption;

    public KeycloakTokenRefreshService(TokenEncryption tokenEncryption) {
        this.tokenEncryption = tokenEncryption;
    }

    public SessionTokens refreshIfNeeded(SessionTokens current, ClientRegistration registration) {
        if (Instant.now().isBefore(current.accessTokenExpiresAt().minusSeconds(30))) {
            return current;
        }
        return refresh(current, registration);
    }

    public SessionTokens refresh(SessionTokens current, ClientRegistration registration) {
        String refreshPlain = tokenEncryption.decrypt(current.encryptedRefreshToken());
        if (!StringUtils.hasText(refreshPlain)) {
            throw new IllegalStateException("No refresh token");
        }
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("grant_type", "refresh_token");
        form.add("refresh_token", refreshPlain);
        form.add("client_id", registration.getClientId());
        String secret = registration.getClientSecret();
        if (StringUtils.hasText(secret)) {
            form.add("client_secret", secret);
        }

        String tokenUri = registration.getProviderDetails().getTokenUri();
        byte[] body = restClient.post()
                .uri(tokenUri)
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(encodeForm(form))
                .retrieve()
                .body(byte[].class);

        if (body == null) {
            throw new IllegalStateException("Empty token response");
        }

        try {
            JsonNode root = objectMapper.readTree(body);
            String accessToken = root.get("access_token").asText();
            int expiresIn = root.has("expires_in") ? root.get("expires_in").asInt() : 120;
            Instant expiresAt = Instant.now().plusSeconds(expiresIn);

            String newRefreshEnc;
            if (root.has("refresh_token") && !root.get("refresh_token").isNull()) {
                newRefreshEnc = tokenEncryption.encrypt(root.get("refresh_token").asText());
            } else {
                newRefreshEnc = current.encryptedRefreshToken();
            }

            return new SessionTokens(accessToken, newRefreshEnc, expiresAt, current.subject());
        } catch (Exception e) {
            throw new IllegalStateException("Token refresh failed", e);
        }
    }

    private String encodeForm(MultiValueMap<String, String> form) {
        StringBuilder sb = new StringBuilder();
        form.forEach((k, vs) -> vs.forEach(v -> {
            if (!sb.isEmpty()) {
                sb.append('&');
            }
            sb.append(java.net.URLEncoder.encode(k, StandardCharsets.UTF_8));
            sb.append('=');
            sb.append(java.net.URLEncoder.encode(v, StandardCharsets.UTF_8));
        }));
        return sb.toString();
    }
}
