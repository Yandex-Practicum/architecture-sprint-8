package com.bionicpro.auth.service;

import com.bionicpro.auth.model.SessionData;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class SessionService {

    private static final Logger log = LoggerFactory.getLogger(SessionService.class);

    @Value("${app.session-max-age}")
    private long sessionMaxAgeSeconds;

    // In-memory session store: sessionId -> SessionData
    // In production, replace with Redis for multi-instance deployments
    private final ConcurrentHashMap<String, SessionData> sessions = new ConcurrentHashMap<>();

    /**
     * Creates a new session binding the provided tokens.
     * Returns the new session ID.
     */
    public String createSession(String accessToken, String refreshToken, Instant accessTokenExpiry) {
        String sessionId = UUID.randomUUID().toString();
        Instant sessionExpiry = Instant.now().plusSeconds(sessionMaxAgeSeconds);
        sessions.put(sessionId, new SessionData(accessToken, refreshToken, accessTokenExpiry, sessionExpiry));
        log.debug("Created session {}, expires at {}", sessionId, sessionExpiry);
        return sessionId;
    }

    /**
     * Retrieves an active session by ID. Returns empty if not found or expired.
     */
    public Optional<SessionData> getSession(String sessionId) {
        if (sessionId == null) return Optional.empty();

        SessionData session = sessions.get(sessionId);
        if (session == null) return Optional.empty();

        if (session.isSessionExpired()) {
            sessions.remove(sessionId);
            log.debug("Session {} expired and removed", sessionId);
            return Optional.empty();
        }
        return Optional.of(session);
    }

    /**
     * Session rotation: removes the old session and creates a new one with the same tokens.
     * Prevents session fixation attacks — every request gets a fresh session ID.
     */
    public String rotateSession(String oldSessionId, SessionData sessionData) {
        sessions.remove(oldSessionId);
        String newSessionId = UUID.randomUUID().toString();
        // Session expiry is preserved from original session to avoid extending it
        sessions.put(newSessionId, sessionData);
        log.debug("Rotated session {} -> {}", oldSessionId, newSessionId);
        return newSessionId;
    }

    /**
     * Invalidates a session (logout).
     */
    public void removeSession(String sessionId) {
        if (sessionId != null) {
            sessions.remove(sessionId);
            log.debug("Removed session {}", sessionId);
        }
    }

    /**
     * Scheduled cleanup of expired sessions every 5 minutes.
     */
    @Scheduled(fixedDelay = 300_000)
    public void cleanExpiredSessions() {
        int before = sessions.size();
        sessions.entrySet().removeIf(e -> e.getValue().isSessionExpired());
        int removed = before - sessions.size();
        if (removed > 0) {
            log.debug("Cleaned {} expired sessions, {} remaining", removed, sessions.size());
        }
    }
}
