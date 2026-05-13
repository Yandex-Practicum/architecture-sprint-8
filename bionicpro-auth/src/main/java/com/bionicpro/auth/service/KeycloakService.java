package com.bionicpro.auth.service;

import com.bionicpro.auth.model.TokenResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.hc.client5.http.classic.methods.HttpPost;
import org.apache.hc.client5.http.entity.UrlEncodedFormEntity;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.core5.http.NameValuePair;
import org.apache.hc.core5.http.message.BasicNameValuePair;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class KeycloakService {

    private static final Logger log = LoggerFactory.getLogger(KeycloakService.class);

    @Value("${keycloak.url}")
    private String keycloakUrl;

    @Value("${keycloak.realm}")
    private String realm;

    @Value("${keycloak.client-id}")
    private String clientId;

    @Value("${keycloak.client-secret}")
    private String clientSecret;

    @Value("${keycloak.callback-url}")
    private String callbackUrl;

    private final ObjectMapper objectMapper = new ObjectMapper();

    // state -> code_verifier, cleaned up after use or expiry
    private final ConcurrentHashMap<String, PkceEntry> pendingPkce = new ConcurrentHashMap<>();

    private record PkceEntry(String codeVerifier, Instant createdAt) {
        boolean isExpired() {
            return Instant.now().isAfter(createdAt.plusSeconds(300)); // 5 min TTL
        }
    }

    /**
     * Builds Keycloak authorization URL with PKCE (S256) challenge.
     * Stores code_verifier server-side, keyed by state parameter.
     */
    public String buildAuthorizationUrl() {
        String codeVerifier = generateCodeVerifier();
        String codeChallenge = generateCodeChallenge(codeVerifier);
        String state = UUID.randomUUID().toString();

        pendingPkce.put(state, new PkceEntry(codeVerifier, Instant.now()));
        cleanStalePkceEntries();

        String baseUrl = keycloakUrl + "/realms/" + realm + "/protocol/openid-connect/auth";
        return baseUrl
                + "?client_id=" + encode(clientId)
                + "&response_type=code"
                + "&redirect_uri=" + encode(callbackUrl)
                + "&state=" + encode(state)
                + "&code_challenge=" + encode(codeChallenge)
                + "&code_challenge_method=S256"
                + "&scope=openid+profile+email";
    }

    /**
     * Exchanges authorization code for tokens using PKCE code_verifier.
     */
    public TokenResponse exchangeCode(String code, String state) throws IOException {
        PkceEntry entry = pendingPkce.remove(state);
        if (entry == null || entry.isExpired()) {
            throw new IllegalStateException("No valid PKCE entry for state: " + state);
        }

        List<NameValuePair> params = new ArrayList<>();
        params.add(new BasicNameValuePair("grant_type", "authorization_code"));
        params.add(new BasicNameValuePair("client_id", clientId));
        params.add(new BasicNameValuePair("client_secret", clientSecret));
        params.add(new BasicNameValuePair("code", code));
        params.add(new BasicNameValuePair("redirect_uri", callbackUrl));
        params.add(new BasicNameValuePair("code_verifier", entry.codeVerifier()));

        return postToTokenEndpoint(params);
    }

    /**
     * Uses refresh_token to obtain a new access_token.
     */
    public TokenResponse refreshAccessToken(String refreshToken) throws IOException {
        List<NameValuePair> params = new ArrayList<>();
        params.add(new BasicNameValuePair("grant_type", "refresh_token"));
        params.add(new BasicNameValuePair("client_id", clientId));
        params.add(new BasicNameValuePair("client_secret", clientSecret));
        params.add(new BasicNameValuePair("refresh_token", refreshToken));

        return postToTokenEndpoint(params);
    }

    /**
     * Computes token expiry from current time + expires_in seconds.
     */
    public Instant computeExpiry(int expiresIn) {
        return Instant.now().plusSeconds(expiresIn);
    }

    private TokenResponse postToTokenEndpoint(List<NameValuePair> params) throws IOException {
        String tokenUrl = keycloakUrl + "/realms/" + realm + "/protocol/openid-connect/token";

        try (CloseableHttpClient httpClient = HttpClients.createDefault()) {
            HttpPost post = new HttpPost(tokenUrl);
            post.setEntity(new UrlEncodedFormEntity(params, StandardCharsets.UTF_8));
            post.setHeader("Content-Type", "application/x-www-form-urlencoded");

            return httpClient.execute(post, response -> {
                byte[] body = response.getEntity().getContent().readAllBytes();
                TokenResponse tokenResponse = objectMapper.readValue(body, TokenResponse.class);
                if (tokenResponse.hasError()) {
                    log.error("Keycloak token error: {} - {}", tokenResponse.getError(), tokenResponse.getError());
                    throw new RuntimeException("Keycloak error: " + tokenResponse.getError());
                }
                return tokenResponse;
            });
        }
    }

    // RFC 7636: code_verifier is 43-128 random URL-safe chars
    private String generateCodeVerifier() {
        byte[] bytes = new byte[32];
        new SecureRandom().nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    // RFC 7636: code_challenge = BASE64URL(SHA256(ASCII(code_verifier)))
    private String generateCodeChallenge(String codeVerifier) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(codeVerifier.getBytes(StandardCharsets.US_ASCII));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }

    private String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private void cleanStalePkceEntries() {
        pendingPkce.entrySet().removeIf(e -> e.getValue().isExpired());
    }
}
