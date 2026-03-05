package bionicpro.auth.session;

/**
 * Абстракция хранилища сессий.
 *
 * В учебном проекте используем InMemorySessionStore (ConcurrentHashMap).
 * В продакшене заменяется на RedisSessionStore без изменения остального кода.
 */
public interface SessionStore {

    /** Сохраняет сессию. */
    void put(String sessionId, SessionData data);

    /**
     * Атомарно извлекает и удаляет сессию.
     * Важно для ротации: между get и delete не должно быть окна,
     * в котором злоумышленник мог бы использовать старый session_id.
     *
     * @return SessionData или null, если сессия не найдена / истекла
     */
    SessionData getAndRemove(String sessionId);

    /** Удаляет сессию (для logout). */
    void remove(String sessionId);

    /** Количество активных сессий (для health check). */
    int size();

    /** Очистка истёкших сессий (вызывается по таймеру). */
    void cleanup();

    // --- PKCE state storage ---
    // state → code_verifier (временное хранилище на время auth flow)

    void putState(String state, String codeVerifier);

    String getAndRemoveState(String state);
}
