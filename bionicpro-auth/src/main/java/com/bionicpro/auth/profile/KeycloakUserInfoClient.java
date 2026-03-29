package com.bionicpro.auth.profile;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class KeycloakUserInfoClient {

    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public KeycloakUserInfoClient(ObjectMapper objectMapper) {
        this.restClient = RestClient.builder().build();
        this.objectMapper = objectMapper;
    }

    /**
     * Данные профиля из Keycloak UserInfo (в т.ч. атрибуты, пришедшие от Яндекс через Identity Brokering).
     */
    public JsonNode fetchUserInfo(String userInfoUri, String accessToken) {
        byte[] body = restClient.get()
                .uri(userInfoUri)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken)
                .accept(MediaType.APPLICATION_JSON)
                .retrieve()
                .body(byte[].class);
        if (body == null || body.length == 0) {
            throw new IllegalStateException("Empty userinfo response");
        }
        try {
            return objectMapper.readTree(body);
        } catch (Exception e) {
            throw new IllegalStateException("Invalid userinfo JSON", e);
        }
    }
}
