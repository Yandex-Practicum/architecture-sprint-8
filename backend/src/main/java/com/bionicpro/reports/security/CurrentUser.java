package com.bionicpro.reports.security;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import java.util.Optional;

/**
 * Идентификатор текущего аутентифицированного пользователя из JWT (Keycloak).
 * Используется для проверки доступа «только к своему отчёту».
 */
public final class CurrentUser {

    private CurrentUser() {
    }

    /**
     * Возвращает идентификатор текущего пользователя для проверки доступа и поиска отчёта.
     * Используется preferred_username (логин), при отсутствии — sub (Keycloak ID).
     */
    public static Optional<String> getUserId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwtAuth) {
            Jwt jwt = jwtAuth.getToken();
            String preferred = jwt.getClaimAsString("preferred_username");
            if (preferred != null && !preferred.isBlank()) {
                return Optional.of(preferred);
            }
            return Optional.ofNullable(jwt.getSubject());
        }
        return Optional.empty();
    }
}
