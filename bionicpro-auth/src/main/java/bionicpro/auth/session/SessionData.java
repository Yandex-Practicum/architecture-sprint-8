package bionicpro.auth.session;

import java.time.Instant;

/**
 * Данные серверной сессии.
 * Хранит токены (которые фронтенд никогда не видит), информацию о пользователе,
 * и временные метки для управления жизненным циклом.
 *
 * Record — immutable. Для обновления создаём новый экземпляр через with-методы.
 */
public record SessionData(
        String accessToken,
        String refreshToken,
        String userId,          // sub из id_token (Keycloak user UUID)
        String username,
        String email,
        String roles,           // comma-separated realm roles
        Instant createdAt,
        Instant lastAccessedAt,
        long accessTokenExpiresAt   // unix timestamp (seconds)
) {

    /** Создать новый SessionData с обновлёнными токенами (после refresh). */
    public SessionData withTokens(String newAccessToken, String newRefreshToken, long newExpiresAt) {
        return new SessionData(
                newAccessToken, newRefreshToken,
                userId, username, email, roles,
                createdAt, Instant.now(), newExpiresAt
        );
    }

    /** Создать новый SessionData с обновлённым lastAccessedAt. */
    public SessionData touch() {
        return new SessionData(
                accessToken, refreshToken,
                userId, username, email, roles,
                createdAt, Instant.now(), accessTokenExpiresAt
        );
    }

    /** Проверяет, истёк ли access_token (с запасом 10 секунд). */
    public boolean isAccessTokenExpired() {
        return Instant.now().getEpochSecond() >= (accessTokenExpiresAt - 10);
    }
}
