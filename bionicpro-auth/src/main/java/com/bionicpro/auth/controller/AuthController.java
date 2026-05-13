package com.bionicpro.auth.controller;

import com.bionicpro.auth.model.TokenResponse;
import com.bionicpro.auth.service.KeycloakService;
import com.bionicpro.auth.service.SessionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.net.URI;
import java.time.Instant;
import java.util.Map;

@RestController
@RequestMapping("/auth")
public class AuthController {

    private static final Logger log = LoggerFactory.getLogger(AuthController.class);
    static final String SESSION_COOKIE = "bionicpro_session";

    private final KeycloakService keycloakService;
    private final SessionService sessionService;

    @Value("${app.frontend-url}")
    private String frontendUrl;

    @Value("${app.session-max-age}")
    private long sessionMaxAge;

    public AuthController(KeycloakService keycloakService, SessionService sessionService) {
        this.keycloakService = keycloakService;
        this.sessionService = sessionService;
    }

    /**
     * Initiates the PKCE authorization flow.
     * Redirects the browser to Keycloak login page.
     */
    @GetMapping("/login")
    public ResponseEntity<Void> login() {
        String authUrl = keycloakService.buildAuthorizationUrl();
        log.debug("Redirecting to Keycloak: {}", authUrl);
        return ResponseEntity.status(HttpStatus.FOUND)
                .location(URI.create(authUrl))
                .build();
    }

    /**
     * OAuth2 callback — Keycloak redirects here after successful login.
     * Exchanges authorization code for tokens (server-side), stores them in session,
     * and returns an HTTP-only session cookie to the browser.
     */
    @GetMapping("/callback")
    public ResponseEntity<Void> callback(
            @RequestParam String code,
            @RequestParam String state,
            @RequestParam(required = false) String error) {

        if (error != null) {
            log.warn("Keycloak returned error: {}", error);
            return ResponseEntity.status(HttpStatus.FOUND)
                    .location(URI.create(frontendUrl + "?auth_error=" + error))
                    .build();
        }

        try {
            TokenResponse tokens = keycloakService.exchangeCode(code, state);
            Instant accessTokenExpiry = keycloakService.computeExpiry(tokens.getExpiresIn());
            String sessionId = sessionService.createSession(
                    tokens.getAccessToken(),
                    tokens.getRefreshToken(),
                    accessTokenExpiry
            );

            ResponseCookie cookie = buildSessionCookie(sessionId, sessionMaxAge);
            return ResponseEntity.status(HttpStatus.FOUND)
                    .header(HttpHeaders.SET_COOKIE, cookie.toString())
                    .location(URI.create(frontendUrl))
                    .build();

        } catch (Exception e) {
            log.error("Token exchange failed", e);
            return ResponseEntity.status(HttpStatus.FOUND)
                    .location(URI.create(frontendUrl + "?auth_error=token_exchange_failed"))
                    .build();
        }
    }

    /**
     * Returns the current authentication status.
     * Used by the frontend to check if the user is logged in.
     */
    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status(
            @CookieValue(value = SESSION_COOKIE, required = false) String sessionId) {

        boolean authenticated = sessionService.getSession(sessionId).isPresent();
        return ResponseEntity.ok(Map.of("authenticated", authenticated));
    }

    /**
     * Invalidates the session and clears the cookie.
     */
    @PostMapping("/logout")
    public ResponseEntity<Void> logout(
            @CookieValue(value = SESSION_COOKIE, required = false) String sessionId) {

        sessionService.removeSession(sessionId);
        // Expire the cookie immediately
        ResponseCookie expiredCookie = buildSessionCookie("", 0);
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, expiredCookie.toString())
                .build();
    }

    static ResponseCookie buildSessionCookie(String sessionId, long maxAge) {
        return ResponseCookie.from(SESSION_COOKIE, sessionId)
                .httpOnly(true)
                // Set secure=true when deployed over HTTPS
                .secure(false)
                .path("/")
                .maxAge(maxAge)
                // Lax allows the cookie to be sent on top-level navigations (OAuth redirect)
                .sameSite("Lax")
                .build();
    }
}
