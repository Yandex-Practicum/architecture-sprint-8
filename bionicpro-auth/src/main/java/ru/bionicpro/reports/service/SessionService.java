package ru.bionicpro.reports.service;

import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import ru.bionicpro.reports.model.AuthSession;
import ru.bionicpro.reports.model.TokenResponse;
import ru.bionicpro.reports.model.UserInfo;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class SessionService {

    private final SessionStorageService sessionStorageService;
    private final KeycloakService keycloakService;
    private final EncryptionService encryptionService;

    public AuthSession createSessionFromAuthCode(String code, String redirectUri, String codeVerifier, HttpSession httpSession) {
        log.info("=== CREATE SESSION START ===");
        log.info("Code: {}", code);

        // 1. Получаем токены
        TokenResponse tokenResponse = keycloakService.exchangeCodeForTokens(code, redirectUri, codeVerifier);
        log.info("Token response - accessToken: {}", tokenResponse.getAccessToken() != null ? "YES" : "NO");
        log.info("Token response - refreshToken: {}", tokenResponse.getRefreshToken() != null ? "YES" : "NO");
        log.info("Token response - expiresIn: {}", tokenResponse.getExpiresIn());

        // 2. Получаем информацию о пользователе
        UserInfo userInfo = keycloakService.getUserInfo(tokenResponse.getAccessToken());
        log.info("User info - username: {}", userInfo.getPreferredUsername());
        log.info("User info - sub: {}", userInfo.getSub());

        // 3. Создаем сессию
        String sessionId = UUID.randomUUID().toString().replace("-", "") + System.currentTimeMillis();
        log.info("Generated session ID: {}", sessionId);

        AuthSession session = new AuthSession();
        session.setSessionId(sessionId);
        session.setUserId(userInfo.getSub());
        session.setUsername(userInfo.getPreferredUsername());
        session.setEmail(userInfo.getEmail());
        session.setAccessToken(tokenResponse.getAccessToken());
        session.setAccessTokenExpiry(Instant.now().plusSeconds(tokenResponse.getExpiresIn()));
        session.setEncryptedRefreshToken(encryptionService.encrypt(tokenResponse.getRefreshToken()));
        session.setRealmRoles(userInfo.getRealmAccess() != null ? userInfo.getRealmAccess().getRoles() : List.of());
        session.setCreatedAt(Instant.now());
        session.setLastRotatedAt(Instant.now());
        session.setActive(true);

        log.info("Session object created - accessToken set: {}", session.getAccessToken() != null);
        log.info("Session object created - expiry: {}", session.getAccessTokenExpiry());

        // 4. Сохраняем в Redis
        sessionStorageService.storeSession(session);
        log.info("Session stored in Redis");

        // 5. Проверяем, что сохранилось
        AuthSession verify = sessionStorageService.getSession(sessionId);
        log.info("Verification from Redis - found: {}", verify != null);
        if (verify != null) {
            log.info("Verification - accessToken present: {}", verify.getAccessToken() != null);
        }

        // 6. Сохраняем sessionId в HTTP сессии
        httpSession.setAttribute("auth_session_id", sessionId);
        log.info("Saved sessionId to HTTP session attribute: {}", sessionId);
        log.info("HTTP Session ID: {}", httpSession.getId());

        // 7. Проверяем, что сохранилось в HTTP сессии
        String retrievedId = (String) httpSession.getAttribute("auth_session_id");
        log.info("Retrieved from HTTP session attribute: {}", retrievedId);

        log.info("=== CREATE SESSION END ===");
        return session;
    }

    public AuthSession getCurrentSession(HttpSession httpSession) {
        String sessionId = (String) httpSession.getAttribute("auth_session_id");
        log.info("Getting current session. Session attribute: {}", sessionId);
        log.info("HTTP Session ID: {}", httpSession.getId());

        if (sessionId == null) {
            log.warn("No auth_session_id found in HTTP session");
            return null;
        }

        AuthSession session = sessionStorageService.getSession(sessionId);
        if (session == null) {
            log.warn("No session found in Redis for ID: {}", sessionId);
        } else {
            log.info("Session found for user: {}", session.getUsername());
            log.info("Access token present: {}", session.getAccessToken() != null);
        }

        return session;
    }

    public String getValidAccessToken(HttpSession httpSession) {
        AuthSession session = getCurrentSession(httpSession);
        if (session == null) {
            log.warn("No session found, cannot get access token");
            return null;
        }

        log.info("Access token expiry: {}", session.getAccessTokenExpiry());
        log.info("Current time: {}", Instant.now());

        // Проверяем, не истек ли токен
        if (Instant.now().isAfter(session.getAccessTokenExpiry())) {
            log.info("Access token expired, refreshing...");
            try {
                String refreshToken = encryptionService.decrypt(session.getEncryptedRefreshToken());
                TokenResponse tokenResponse = keycloakService.refreshAccessToken(refreshToken);

                session.setAccessToken(tokenResponse.getAccessToken());
                session.setAccessTokenExpiry(Instant.now().plusSeconds(tokenResponse.getExpiresIn()));
                session.setEncryptedRefreshToken(encryptionService.encrypt(tokenResponse.getRefreshToken()));
                sessionStorageService.storeSession(session);

                log.info("Access token refreshed successfully");
            } catch (Exception e) {
                log.error("Failed to refresh token", e);
                return null;
            }
        }

        return session.getAccessToken();
    }

    public void rotateSession(HttpSession httpSession) {
        String currentSessionId = (String) httpSession.getAttribute("auth_session_id");
        if (currentSessionId == null) return;

        String newSessionId = generateSessionId();
        AuthSession currentSession = sessionStorageService.getSession(currentSessionId);

        if (currentSession != null) {
            currentSession.setSessionId(newSessionId);
            currentSession.setLastRotatedAt(Instant.now());
            sessionStorageService.storeSession(currentSession);
            sessionStorageService.deleteSession(currentSessionId);
            httpSession.setAttribute("auth_session_id", newSessionId);
            log.info("Session rotated from {} to {}", currentSessionId, newSessionId);
        }
    }

    public void invalidateSession(HttpSession httpSession) {
        String sessionId = (String) httpSession.getAttribute("auth_session_id");
        if (sessionId != null) {
            AuthSession session = sessionStorageService.getSession(sessionId);
            if (session != null) {
                try {
                    String refreshToken = encryptionService.decrypt(session.getEncryptedRefreshToken());
                    keycloakService.logout(refreshToken);
                } catch (Exception e) {
                    log.warn("Failed to logout from Keycloak: {}", e.getMessage());
                }
                sessionStorageService.deleteSession(sessionId);
                log.info("Session invalidated: {}", sessionId);
            }
        }
        httpSession.invalidate();
    }

    private String generateSessionId() {
        return UUID.randomUUID().toString().replace("-", "") + System.currentTimeMillis();
    }
}