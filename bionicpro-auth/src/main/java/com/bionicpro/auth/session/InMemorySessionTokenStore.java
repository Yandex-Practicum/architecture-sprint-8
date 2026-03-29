package com.bionicpro.auth.session;

import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class InMemorySessionTokenStore implements SessionTokenStore {

    private final Map<String, SessionTokens> sessions = new ConcurrentHashMap<>();

    @Override
    public void save(String sessionId, SessionTokens tokens) {
        sessions.put(sessionId, tokens);
    }

    @Override
    public Optional<SessionTokens> find(String sessionId) {
        return Optional.ofNullable(sessions.get(sessionId));
    }

    @Override
    public void remove(String sessionId) {
        sessions.remove(sessionId);
    }

    @Override
    public void rekey(String oldSessionId, String newSessionId) {
        SessionTokens tokens = sessions.remove(oldSessionId);
        if (tokens != null) {
            sessions.put(newSessionId, tokens);
        }
    }
}
