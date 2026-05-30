package ru.bionicpro.reports.service;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;
import ru.bionicpro.reports.model.TokenResponse;
import ru.bionicpro.reports.model.UserInfo;

@Service
@Slf4j
public class KeycloakService {

    private final RestTemplate restTemplate;
    private final ObjectMapper keycloakMapper;

    @Value("${bionicpro.keycloak.token-uri}")
    private String tokenUri;

    @Value("${bionicpro.keycloak.userinfo-uri}")
    private String userInfoUri;

    @Value("${bionicpro.keycloak.logout-uri}")
    private String logoutUri;

    @Value("${bionicpro.keycloak.client-id}")
    private String clientId;

    @Value("${bionicpro.keycloak.client-secret}")
    private String clientSecret;

    public KeycloakService(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
        this.keycloakMapper = new ObjectMapper();
        this.keycloakMapper.setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);
        this.keycloakMapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    }

    public TokenResponse exchangeCodeForTokens(String code, String redirectUri, String codeVerifier) {
        log.info("Exchanging code for tokens with PKCE");

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("grant_type", "authorization_code");
        body.add("code", code);
        body.add("client_id", clientId);
        body.add("client_secret", clientSecret);
        body.add("redirect_uri", redirectUri);
        if (codeVerifier != null) {
            body.add("code_verifier", codeVerifier);
        }

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<String> response = restTemplate.exchange(
                    tokenUri,
                    HttpMethod.POST,
                    request,
                    String.class
            );

            log.info("Token response received");
            return keycloakMapper.readValue(response.getBody(), TokenResponse.class);

        } catch (Exception e) {
            log.error("Failed to exchange code for tokens", e);
            throw new RuntimeException("Failed to exchange code for tokens", e);
        }
    }

    public TokenResponse refreshAccessToken(String refreshToken) {
        log.info("Refreshing access token");

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("grant_type", "refresh_token");
        body.add("refresh_token", refreshToken);
        body.add("client_id", clientId);
        body.add("client_secret", clientSecret);

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<String> response = restTemplate.exchange(
                    tokenUri,
                    HttpMethod.POST,
                    request,
                    String.class
            );

            log.info("Token refreshed successfully");
            return keycloakMapper.readValue(response.getBody(), TokenResponse.class);

        } catch (Exception e) {
            log.error("Failed to refresh access token", e);
            throw new RuntimeException("Failed to refresh access token", e);
        }
    }

    public UserInfo getUserInfo(String accessToken) {
        log.info("Getting user info with token");

        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + accessToken);
        headers.set("Accept", "application/json");

        HttpEntity<?> request = new HttpEntity<>(headers);

        try {
            ResponseEntity<String> response = restTemplate.exchange(
                    userInfoUri,
                    HttpMethod.GET,
                    request,
                    String.class
            );

            log.info("User info response received");
            return keycloakMapper.readValue(response.getBody(), UserInfo.class);

        } catch (Exception e) {
            log.error("Failed to get user info", e);
            throw new RuntimeException("Failed to get user info: " + e.getMessage(), e);
        }
    }

    public void logout(String refreshToken) {
        log.info("Logging out from Keycloak");

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("refresh_token", refreshToken);
        body.add("client_id", clientId);
        body.add("client_secret", clientSecret);

        HttpEntity<MultiValueMap<String, String>> request = new HttpEntity<>(body, headers);

        try {
            restTemplate.exchange(logoutUri, HttpMethod.POST, request, String.class);
            log.info("Logged out successfully");
        } catch (Exception e) {
            log.warn("Failed to logout: {}", e.getMessage());
        }
    }
}

//@Service
//@RequiredArgsConstructor
//@Slf4j
//public class KeycloakService {
//
//    private final WebClient webClient;
//    private final ObjectMapper objectMapper;
//
//    @Value("${bionicpro.keycloak.token-uri}")
//    private String tokenUri;
//
//    @Value("${bionicpro.keycloak.userinfo-uri}")
//    private String userInfoUri;
//
//    @Value("${bionicpro.keycloak.logout-uri}")
//    private String logoutUri;
//
//    @Value("${bionicpro.keycloak.client-id}")
//    private String clientId;
//
//    @Value("${bionicpro.keycloak.client-secret}")
//    private String clientSecret;
//
//    public TokenResponse exchangeCodeForTokens(String code, String redirectUri, String codeVerifier) {
//        log.debug("Exchanging code for tokens with PKCE");
//
//        try {
//            String body = "grant_type=authorization_code" +
//                    "&code=" + code +
//                    "&client_id=" + clientId +
//                    "&client_secret=" + clientSecret +
//                    "&redirect_uri=" + redirectUri +
//                    "&code_verifier=" + codeVerifier;
//
//            log.debug("Token request body: {}", body.replace(clientSecret, "***"));
//
//            String response = webClient.post()
//                    .uri(tokenUri)
//                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
//                    .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
//                    .bodyValue(body)
//                    .retrieve()
//                    .bodyToMono(String.class)
//                    .block();
//
//            log.debug("Token response received");
//            return objectMapper.readValue(response, TokenResponse.class);
//
//        } catch (Exception e) {
//            log.error("Failed to exchange code for tokens", e);
//            throw new RuntimeException("Failed to exchange code for tokens: " + e.getMessage(), e);
//        }
//    }
//
//    public TokenResponse refreshAccessToken(String refreshToken) {
//        log.debug("Refreshing access token");
//
//        try {
//            String body = "grant_type=refresh_token" +
//                    "&refresh_token=" + refreshToken +
//                    "&client_id=" + clientId +
//                    "&client_secret=" + clientSecret;
//
//            String response = webClient.post()
//                    .uri(tokenUri)
//                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
//                    .bodyValue(body)
//                    .retrieve()
//                    .bodyToMono(String.class)
//                    .block();
//
//            return objectMapper.readValue(response, TokenResponse.class);
//
//        } catch (Exception e) {
//            log.error("Failed to refresh access token", e);
//            throw new RuntimeException("Failed to refresh access token", e);
//        }
//    }
//
//    public UserInfo getUserInfo(String accessToken) {
//        log.debug("Getting user info with token: {}", accessToken);
//        log.debug("Getting user info with token: {}...",
//                accessToken != null ? accessToken.substring(0, Math.min(20, accessToken.length())) : "null");
//
//        try {
//            String authHeader = "Bearer " + accessToken;
//            String response = webClient.get()
//                    .uri(userInfoUri)
//                    .header(HttpHeaders.AUTHORIZATION, authHeader)
//                    .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
//                    .retrieve()
//                    .bodyToMono(String.class)
//                    .block();
//
//            log.debug("User info response: {}", response);
//            return objectMapper.readValue(response, UserInfo.class);
//
//        } catch (WebClientResponseException e) {
//            log.error("User info error: status={}, body={}", e.getStatusCode(), e.getResponseBodyAsString());
//            throw new RuntimeException("Failed to get user info: " + e.getResponseBodyAsString(), e);
//        } catch (Exception e) {
//            log.error("Failed to get user info", e);
//            throw new RuntimeException("Failed to get user info", e);
//        }
//    }
//
//    public void logout(String refreshToken) {
//        log.debug("Logging out from Keycloak");
//
//        try {
//            String body = "refresh_token=" + refreshToken +
//                    "&client_id=" + clientId +
//                    "&client_secret=" + clientSecret;
//
//            webClient.post()
//                    .uri(logoutUri)
//                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
//                    .bodyValue(body)
//                    .retrieve()
//                    .toBodilessEntity()
//                    .block();
//
//            log.debug("Logged out from Keycloak successfully");
//
//        } catch (Exception e) {
//            log.warn("Failed to logout from Keycloak: {}", e.getMessage());
//        }
//    }
//}
