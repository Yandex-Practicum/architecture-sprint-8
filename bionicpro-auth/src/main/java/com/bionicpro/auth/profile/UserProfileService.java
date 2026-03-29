package com.bionicpro.auth.profile;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.Instant;
import java.util.Optional;

@Service
public class UserProfileService {

    private static final String REGISTRATION_ID = "keycloak";

    private final UserYandexProfileRepository repository;
    private final KeycloakUserInfoClient userInfoClient;
    private final ClientRegistrationRepository clientRegistrationRepository;
    private final ObjectMapper objectMapper;

    @Value("${spring.security.oauth2.client.provider.keycloak.user-info-uri}")
    private String userInfoUri;

    public UserProfileService(
            UserYandexProfileRepository repository,
            KeycloakUserInfoClient userInfoClient,
            ClientRegistrationRepository clientRegistrationRepository,
            ObjectMapper objectMapper) {
        this.repository = repository;
        this.userInfoClient = userInfoClient;
        this.clientRegistrationRepository = clientRegistrationRepository;
        this.objectMapper = objectMapper;
    }

    public JsonNode loadUserInfo(String accessToken) {
        String uri = resolveUserInfoUri();
        return userInfoClient.fetchUserInfo(uri, accessToken);
    }

    private String resolveUserInfoUri() {
        var reg = clientRegistrationRepository.findByRegistrationId(REGISTRATION_ID);
        if (reg != null && StringUtils.hasText(reg.getProviderDetails().getUserInfoEndpoint().getUri())) {
            return reg.getProviderDetails().getUserInfoEndpoint().getUri();
        }
        return userInfoUri;
    }

    public ProfileStatusDto buildStatus(String subject, String accessToken) {
        Optional<UserYandexProfile> row = repository.findByKeycloakSubject(subject);
        if (row.isPresent() && row.get().isConsentAccepted()) {
            return new ProfileStatusDto(false, true, null);
        }

        JsonNode userInfo = loadUserInfo(accessToken);
        PreviewDto preview = new PreviewDto(
                text(userInfo, "email"),
                firstNonEmpty(userInfo, "name", "preferred_username", "given_name"));
        boolean needs = row.map(r -> !r.isConsentAccepted()).orElse(true);
        return new ProfileStatusDto(needs, false, preview);
    }

    @Transactional
    public void recordConsent(String subject, String accessToken, boolean accept) {
        JsonNode userInfo = accept ? loadUserInfo(accessToken) : objectMapper.createObjectNode();
        Instant now = Instant.now();

        UserYandexProfile row = repository.findByKeycloakSubject(subject).orElseGet(UserYandexProfile::new);
        row.setKeycloakSubject(subject);
        row.setConsentAccepted(accept);
        row.setConsentAcceptedAt(accept ? now : null);
        row.setUpdatedAt(now);

        if (accept) {
            row.setProfileJson(userInfo.toString());
            row.setEmail(text(userInfo, "email"));
            row.setDisplayName(firstNonEmpty(userInfo, "name", "preferred_username"));
            row.setFirstName(text(userInfo, "given_name"));
            row.setLastName(text(userInfo, "family_name"));
            row.setAvatarUrl(text(userInfo, "picture"));
            row.setYandexId(firstNonEmpty(userInfo, "yandex_id", "yandexId", "psuid"));
            if (!StringUtils.hasText(row.getYandexId())) {
                row.setYandexId(text(userInfo, "sub"));
            }
        } else {
            row.setProfileJson(null);
            row.setEmail(null);
            row.setDisplayName(null);
            row.setFirstName(null);
            row.setLastName(null);
            row.setAvatarUrl(null);
            row.setYandexId(null);
        }

        repository.save(row);
    }

    static String text(JsonNode root, String field) {
        if (root == null || !root.has(field) || root.get(field).isNull()) {
            return null;
        }
        return root.get(field).asText(null);
    }

    static String firstNonEmpty(JsonNode root, String... fields) {
        for (String f : fields) {
            String v = text(root, f);
            if (StringUtils.hasText(v)) {
                return v;
            }
        }
        return null;
    }

    public record ProfileStatusDto(boolean needsConsent, boolean consentAccepted, PreviewDto preview) {}

    public record PreviewDto(String email, String displayName) {
        static PreviewDto fromUserInfo(JsonNode userInfo) {
            String email = text(userInfo, "email");
            String display = firstNonEmpty(userInfo, "name", "preferred_username", "given_name");
            return new PreviewDto(email, display);
        }
    }
}
