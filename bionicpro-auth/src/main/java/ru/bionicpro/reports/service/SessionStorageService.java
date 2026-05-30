package ru.bionicpro.reports.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import ru.bionicpro.reports.model.AuthSession;

import java.util.concurrent.TimeUnit;

@Service
@RequiredArgsConstructor
@Slf4j
public class SessionStorageService {

    private final RedisTemplate<String, Object> redisTemplate;
    private static final String SESSION_KEY_PREFIX = "auth:session:";

    public void storeSession(AuthSession session) {
        String key = SESSION_KEY_PREFIX + session.getSessionId();
        redisTemplate.opsForValue().set(key, session, 3600, TimeUnit.SECONDS);
        log.info("Session stored in Redis: key={}, userId={}", key, session.getUserId());

        // Проверяем, что сохранилось
        AuthSession saved = getSession(session.getSessionId());
        if (saved != null) {
            log.info("Verified session saved in Redis");
        } else {
            log.error("Failed to verify session in Redis!");
        }
    }

    public AuthSession getSession(String sessionId) {
        String key = SESSION_KEY_PREFIX + sessionId;
        Object session = redisTemplate.opsForValue().get(key);
        log.debug("Retrieved session from Redis: key={}, found={}", key, session != null);
        return session instanceof AuthSession ? (AuthSession) session : null;
    }

    public void deleteSession(String sessionId) {
        String key = SESSION_KEY_PREFIX + sessionId;
        redisTemplate.delete(key);
        log.debug("Session deleted from Redis: {}", sessionId);
    }
}
