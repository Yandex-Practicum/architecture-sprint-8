package com.bionicpro.auth.controller;

import com.bionicpro.auth.model.SessionData;
import com.bionicpro.auth.model.TokenResponse;
import com.bionicpro.auth.service.KeycloakService;
import com.bionicpro.auth.service.SessionService;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.time.Instant;
import java.util.Optional;

import static com.bionicpro.auth.controller.AuthController.SESSION_COOKIE;

/**
 * Proxies requests to the Reports API, injecting the Bearer access_token from the session.
 *
 * On every request:
 *  1. Validates session cookie.
 *  2. Refreshes access_token if expired (using refresh_token).
 *  3. Forwards request to Reports API with Authorization header.
 *  4. Rotates session ID (session fixation prevention).
 *  5. Returns response with updated session cookie.
 */
@RestController
@RequestMapping("/api")
public class ApiProxyController {

    private static final Logger log = LoggerFactory.getLogger(ApiProxyController.class);

    private final SessionService sessionService;
    private final KeycloakService keycloakService;
    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${reports-api.url}")
    private String reportsApiUrl;

    @Value("${app.session-max-age}")
    private long sessionMaxAge;

    public ApiProxyController(SessionService sessionService, KeycloakService keycloakService) {
        this.sessionService = sessionService;
        this.keycloakService = keycloakService;
    }

    @GetMapping("/reports")
    public ResponseEntity<?> getReports(
            @CookieValue(value = SESSION_COOKIE, required = false) String sessionId) {

        SessionData session = resolveSession(sessionId);
        if (session == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body("Authentication required. Please login at /auth/login");
        }

        // Refresh access_token if it is close to expiry
        String accessToken = getValidAccessToken(session, sessionId);
        if (accessToken == null) {
            sessionService.removeSession(sessionId);
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body("Session expired. Please login again.");
        }

        // Proxy the request to the actual Reports API
        ResponseEntity<Object> apiResponse = callReportsApi(accessToken, "/reports");

        // Session rotation — rebind tokens to a new session ID on every successful request
        String newSessionId = sessionService.rotateSession(sessionId, session);
        ResponseCookie newCookie = AuthController.buildSessionCookie(newSessionId, sessionMaxAge);

        return ResponseEntity.status(apiResponse.getStatusCode())
                .header(HttpHeaders.SET_COOKIE, newCookie.toString())
                .body(apiResponse.getBody());
    }

    // ---- helpers ----

    private SessionData resolveSession(String sessionId) {
        if (sessionId == null || sessionId.isBlank()) return null;
        Optional<SessionData> opt = sessionService.getSession(sessionId);
        return opt.orElse(null);
    }

    /**
     * Returns a valid access_token, refreshing via refresh_token when needed.
     * Returns null if the refresh also fails (session must be terminated).
     */
    private String getValidAccessToken(SessionData session, String sessionId) {
        if (!session.isAccessTokenExpired()) {
            return session.getAccessToken();
        }

        log.debug("Access token expired for session {}, refreshing...", sessionId);
        try {
            TokenResponse refreshed = keycloakService.refreshAccessToken(session.getRefreshToken());
            Instant newExpiry = keycloakService.computeExpiry(refreshed.getExpiresIn());
            session.updateTokens(refreshed.getAccessToken(), refreshed.getRefreshToken(), newExpiry);
            return refreshed.getAccessToken();
        } catch (Exception e) {
            log.warn("Failed to refresh token for session {}: {}", sessionId, e.getMessage());
            return null;
        }
    }

    private ResponseEntity<Object> callReportsApi(String accessToken, String path) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(accessToken);
        HttpEntity<Void> entity = new HttpEntity<>(headers);

        try {
            return restTemplate.exchange(
                    reportsApiUrl + path,
                    HttpMethod.GET,
                    entity,
                    Object.class
            );
        } catch (Exception e) {
            log.error("Reports API call failed: {}", e.getMessage());
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .body("Reports service unavailable");
        }
    }
}
