package com.bionicpro.auth.web;

import com.bionicpro.auth.config.AppProperties;
import com.bionicpro.auth.oauth.KeycloakTokenRefreshService;
import com.bionicpro.auth.session.SessionTokenStore;
import com.bionicpro.auth.session.SessionTokens;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.lang.NonNull;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.time.Duration;
import java.util.Arrays;
import java.util.Optional;
import java.util.UUID;

/**
 * Проверяет сессионную cookie, при необходимости обновляет access_token через refresh_token,
 * выполняет ротацию session id на каждом запросе к /api/** (защита от session fixation).
 */
@Component
public class SessionAuthenticationFilter extends OncePerRequestFilter {

    public static final String ATTR_ACCESS_TOKEN = "BIONIC_ACCESS_TOKEN";
    public static final String ATTR_SUBJECT = "BIONIC_SUBJECT";
    public static final String HEADER_SESSION_ID = "X-Session-Id";

    private static final String REGISTRATION_ID = "keycloak";

    private final SessionTokenStore sessionTokenStore;
    private final KeycloakTokenRefreshService tokenRefreshService;
    private final ClientRegistrationRepository clientRegistrationRepository;
    private final AppProperties appProperties;

    public SessionAuthenticationFilter(
            SessionTokenStore sessionTokenStore,
            KeycloakTokenRefreshService tokenRefreshService,
            ClientRegistrationRepository clientRegistrationRepository,
            AppProperties appProperties) {
        this.sessionTokenStore = sessionTokenStore;
        this.tokenRefreshService = tokenRefreshService;
        this.clientRegistrationRepository = clientRegistrationRepository;
        this.appProperties = appProperties;
    }

    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull FilterChain filterChain) throws ServletException, IOException {

        if (!isApiPath(request)) {
            filterChain.doFilter(request, response);
            return;
        }

        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            filterChain.doFilter(request, response);
            return;
        }

        if (isLogoutPath(request)) {
            filterChain.doFilter(request, response);
            return;
        }

        Optional<String> cookieSessionId = readSessionCookie(request);
        if (cookieSessionId.isEmpty()) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            return;
        }

        Optional<SessionTokens> tokensOpt = sessionTokenStore.find(cookieSessionId.get());
        if (tokensOpt.isEmpty()) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            return;
        }

        ClientRegistration registration = clientRegistrationRepository.findByRegistrationId(REGISTRATION_ID);
        if (registration == null) {
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
            return;
        }

        SessionTokens tokens;
        try {
            tokens = tokenRefreshService.refreshIfNeeded(tokensOpt.get(), registration);
        } catch (Exception e) {
            sessionTokenStore.remove(cookieSessionId.get());
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            return;
        }

        String newSessionId = UUID.randomUUID().toString();
        sessionTokenStore.remove(cookieSessionId.get());
        sessionTokenStore.save(newSessionId, tokens);

        appendSessionCookie(response, newSessionId);
        response.setHeader(HEADER_SESSION_ID, newSessionId);

        request.setAttribute(ATTR_ACCESS_TOKEN, tokens.accessToken());
        request.setAttribute(ATTR_SUBJECT, tokens.subject());

        filterChain.doFilter(request, response);
    }

    private boolean isApiPath(HttpServletRequest request) {
        String uri = request.getRequestURI();
        String context = request.getContextPath();
        String path = context != null && !context.isEmpty() ? uri.substring(context.length()) : uri;
        return path.startsWith("/api/");
    }

    private boolean isLogoutPath(HttpServletRequest request) {
        String uri = request.getRequestURI();
        String context = request.getContextPath();
        String path = context != null && !context.isEmpty() ? uri.substring(context.length()) : uri;
        return path.equals("/api/logout");
    }

    private Optional<String> readSessionCookie(HttpServletRequest request) {
        if (request.getCookies() == null) {
            return Optional.empty();
        }
        return Arrays.stream(request.getCookies())
                .filter(c -> appProperties.getSessionCookieName().equals(c.getName()))
                .map(Cookie::getValue)
                .findFirst();
    }

    private void appendSessionCookie(HttpServletResponse response, String sessionId) {
        ResponseCookie cookie = ResponseCookie.from(appProperties.getSessionCookieName(), sessionId)
                .httpOnly(true)
                .secure(appProperties.isCookieSecure())
                .path("/")
                .maxAge(Duration.ofSeconds(appProperties.getSessionMaxAgeSeconds()))
                .sameSite("Lax")
                .build();
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());
    }
}
