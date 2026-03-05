package bionicpro.auth.session;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;

/**
 * In-memory реализация SessionStore на ConcurrentHashMap.
 *
 * Подходит для учебного проекта / одного инстанса.
 * В продакшене заменить на Redis (TTL, масштабирование, персистенция).
 */
public class InMemorySessionStore implements SessionStore {

    private static final Logger log = LoggerFactory.getLogger(InMemorySessionStore.class);

    private final ConcurrentHashMap<String, SessionData> sessions = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, StateEntry> states = new ConcurrentHashMap<>();
    private final int sessionTtlSeconds;

    /** TTL для PKCE state (5 минут — достаточно на весь auth flow). */
    private static final int STATE_TTL_SECONDS = 300;

    public InMemorySessionStore(int sessionTtlSeconds) {
        this.sessionTtlSeconds = sessionTtlSeconds;
    }

    @Override
    public void put(String sessionId, SessionData data) {
        sessions.put(sessionId, data);
        log.debug("Session created: {}... (user: {})", sessionId.substring(0, 8), data.username());
    }

    @Override
    public SessionData getAndRemove(String sessionId) {
        var data = sessions.remove(sessionId); // Атомарно!
        if (data == null) {
            log.debug("Session not found: {}...", sessionId.substring(0, Math.min(8, sessionId.length())));
            return null;
        }

        // Проверяем TTL
        if (isSessionExpired(data)) {
            log.debug("Session expired: {}... (user: {})", sessionId.substring(0, 8), data.username());
            return null;
        }

        return data;
    }

    @Override
    public void remove(String sessionId) {
        var removed = sessions.remove(sessionId);
        if (removed != null) {
            log.debug("Session removed: {}... (user: {})", sessionId.substring(0, 8), removed.username());
        }
    }

    @Override
    public int size() {
        return sessions.size();
    }

    @Override
    public void cleanup() {
        int beforeSize = sessions.size();
        sessions.entrySet().removeIf(e -> isSessionExpired(e.getValue()));
        states.entrySet().removeIf(e -> e.getValue().isExpired());
        int removed = beforeSize - sessions.size();
        if (removed > 0) {
            log.info("Cleanup: removed {} expired sessions, {} remaining", removed, sessions.size());
        }
    }

    // --- PKCE state ---

    @Override
    public void putState(String state, String codeVerifier) {
        states.put(state, new StateEntry(codeVerifier, Instant.now()));
    }

    @Override
    public String getAndRemoveState(String state) {
        var entry = states.remove(state);
        if (entry == null || entry.isExpired()) {
            return null;
        }
        return entry.codeVerifier();
    }

    // --- Private ---

    private boolean isSessionExpired(SessionData data) {
        return Duration.between(data.lastAccessedAt(), Instant.now()).getSeconds() > sessionTtlSeconds;
    }

    private record StateEntry(String codeVerifier, Instant createdAt) {
        boolean isExpired() {
            return Duration.between(createdAt, Instant.now()).getSeconds() > STATE_TTL_SECONDS;
        }
    }
}
