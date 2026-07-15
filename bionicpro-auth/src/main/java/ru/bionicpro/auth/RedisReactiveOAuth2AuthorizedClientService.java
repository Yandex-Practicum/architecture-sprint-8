package ru.bionicpro.auth;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.ReactiveRedisTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClient;
import org.springframework.security.oauth2.client.ReactiveOAuth2AuthorizedClientService;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ReactiveClientRegistrationRepository;
import org.springframework.security.oauth2.core.OAuth2AccessToken;
import org.springframework.security.oauth2.core.OAuth2RefreshToken;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import javax.crypto.Cipher;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

@Component
public class RedisReactiveOAuth2AuthorizedClientService implements ReactiveOAuth2AuthorizedClientService {

    private static final int IV_LENGTH = 12;

    private static final String TRANSFORMATION = "AES/GCM/NoPadding";

    private static final int GCM_TAG_LENGTH = 128;

    private final ReactiveRedisTemplate<String, String> redisTemplate;

    private final ReactiveClientRegistrationRepository clientRegistrationRepository;

    private final SecretKey secretKey;

    private final SecureRandom secureRandom = new SecureRandom();

    public RedisReactiveOAuth2AuthorizedClientService(
            ReactiveRedisTemplate<String, String> redisTemplate,
            ReactiveClientRegistrationRepository clientRegistrationRepository,
            @Value("${app.encryption-key}") String encryptionKey
    ) {
        this.redisTemplate = redisTemplate;
        this.clientRegistrationRepository = clientRegistrationRepository;
        this.secretKey = new SecretKeySpec(Base64.getDecoder().decode(encryptionKey), "AES");
    }

    @Override
    @SuppressWarnings("unchecked")
    public <T extends OAuth2AuthorizedClient> Mono<T> loadAuthorizedClient(
            String clientRegistrationId,
            String principalName
    ) {
        return (Mono<T>) redisTemplate.<String, String>opsForHash().entries(buildKey(clientRegistrationId, principalName))
                .collectMap(Map.Entry::getKey, Map.Entry::getValue)
                .flatMap(this::convertAuthorizedClient);
    }

    private Mono<OAuth2AuthorizedClient> convertAuthorizedClient(Map<String, String> data) {
        return clientRegistrationRepository.findByRegistrationId(data.get("clientRegistrationId"))
                .map(clientRegistration -> convertAuthorizedClient(data, clientRegistration));
    }

    private OAuth2AuthorizedClient convertAuthorizedClient(
            Map<String, String> data,
            ClientRegistration clientRegistration
    ) {
        String accessTokenIssuedAt = data.get("accessTokenIssuedAt");
        String accessTokenExpiresAt = data.get("accessTokenExpiresAt");
        String refreshTokenValue = data.get("refreshTokenValue");
        String refreshTokenIssuedAt = data.get("refreshTokenIssuedAt");

        OAuth2AccessToken accessToken = new OAuth2AccessToken(
                new OAuth2AccessToken.TokenType(data.get("accessTokenType")),
                decrypt(data.get("accessTokenValue")),
                accessTokenIssuedAt != null ? Instant.parse(accessTokenIssuedAt) : null,
                accessTokenExpiresAt != null ? Instant.parse(accessTokenExpiresAt) : null,
                Set.of(data.get("accessTokenScopes").split(","))
        );
        OAuth2RefreshToken refreshToken = null;
        if (refreshTokenValue != null) {
            refreshToken = new OAuth2RefreshToken(
                    decrypt(refreshTokenValue),
                    refreshTokenIssuedAt != null ? Instant.parse(refreshTokenIssuedAt) : null
            );
        }

        return new OAuth2AuthorizedClient(clientRegistration, data.get("principalName"), accessToken, refreshToken);
    }

    @Override
    public Mono<Void> saveAuthorizedClient(OAuth2AuthorizedClient authorizedClient, Authentication principal) {
        String clientRegistrationId = authorizedClient.getClientRegistration().getRegistrationId();
        String principalName = principal.getName();

        OAuth2AccessToken accessToken = authorizedClient.getAccessToken();
        Instant accessTokenIssuedAt = accessToken.getIssuedAt();
        Instant accessTokenExpiresAt = accessToken.getExpiresAt();

        OAuth2RefreshToken refreshToken = authorizedClient.getRefreshToken();
        Instant refreshTokenIssuedAt = refreshToken != null ? refreshToken.getIssuedAt() : null;

        Map<String, String> data = new HashMap<>();
        data.put("clientRegistrationId", clientRegistrationId);
        data.put("principalName", principalName);
        data.put("accessTokenType", accessToken.getTokenType().getValue());
        data.put("accessTokenValue", encrypt(accessToken.getTokenValue()));
        data.put("accessTokenIssuedAt", accessTokenIssuedAt != null ? accessTokenIssuedAt.toString() : null);
        data.put("accessTokenExpiresAt", accessTokenExpiresAt != null ? accessTokenExpiresAt.toString() : null);
        data.put("accessTokenScopes", String.join(",", accessToken.getScopes()));
        data.put("refreshTokenValue", refreshToken != null ? encrypt(refreshToken.getTokenValue()) : null);
        data.put("refreshTokenIssuedAt", refreshTokenIssuedAt != null ? refreshTokenIssuedAt.toString() : null);

        return redisTemplate.opsForHash().putAll(buildKey(clientRegistrationId, principalName), data)
                .then();
    }

    @Override
    public Mono<Void> removeAuthorizedClient(String clientRegistrationId, String principalName) {
        return redisTemplate.opsForHash().delete(buildKey(clientRegistrationId, principalName))
                .then();
    }

    private String buildKey(String clientRegistrationId, String principalName) {
        return "oauth2_authorized_client:" + clientRegistrationId + ":" + principalName;
    }

    private String encrypt(String data) {
        byte[] iv = new byte[IV_LENGTH];
        secureRandom.nextBytes(iv);

        try {
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.ENCRYPT_MODE, secretKey, new GCMParameterSpec(GCM_TAG_LENGTH, iv));

            byte[] cipherText = cipher.doFinal(data.getBytes());
            byte[] result = new byte[iv.length + cipherText.length];
            System.arraycopy(iv, 0, result, 0, iv.length);
            System.arraycopy(cipherText, 0, result, iv.length, cipherText.length);

            return Base64.getEncoder().encodeToString(result);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    private String decrypt(String data) {
        byte[] input = Base64.getDecoder().decode(data);

        byte[] iv = new byte[IV_LENGTH];
        System.arraycopy(input, 0, iv, 0, IV_LENGTH);

        byte[] cipherText = new byte[input.length - IV_LENGTH];
        System.arraycopy(input, IV_LENGTH, cipherText, 0, cipherText.length);

        try {
            Cipher cipher = Cipher.getInstance(TRANSFORMATION);
            cipher.init(Cipher.DECRYPT_MODE, secretKey, new GCMParameterSpec(GCM_TAG_LENGTH, iv));

            return new String(cipher.doFinal(cipherText));
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

}
