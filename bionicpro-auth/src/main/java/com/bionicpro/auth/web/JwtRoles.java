package com.bionicpro.auth.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;

final class JwtRoles {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private JwtRoles() {
    }

    static List<String> fromAccessToken(String jwt) {
        List<String> roles = new ArrayList<>();
        String[] parts = jwt.split("\\.");
        if (parts.length < 2) {
            return roles;
        }
        try {
            byte[] payload = Base64.getUrlDecoder().decode(parts[1]);
            JsonNode root = MAPPER.readTree(new String(payload, StandardCharsets.UTF_8));
            JsonNode realmRoles = root.path("realm_access").path("roles");
            realmRoles.forEach(node -> roles.add(node.asText()));
        } catch (IllegalArgumentException | java.io.IOException ignored) {
        }
        return roles;
    }
}
