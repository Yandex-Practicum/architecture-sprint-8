package com.bionicpro.auth.session;

import java.util.Optional;

public interface SessionTokenStore {

    void save(String sessionId, SessionTokens tokens);

    Optional<SessionTokens> find(String sessionId);

    void remove(String sessionId);

    /**
     * Перенос токенов на новый session id (ротация сессии).
     */
    void rekey(String oldSessionId, String newSessionId);
}
