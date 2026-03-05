package bionicpro.auth.handler;

import bionicpro.auth.keycloak.KeycloakClient;
import bionicpro.auth.session.SessionData;
import bionicpro.auth.session.SessionStore;
import bionicpro.auth.util.CookieUtil;
import bionicpro.auth.util.PkceUtil;
import io.javalin.http.Context;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Instant;

import static bionicpro.auth.AuthServer.*;

/**
 * GET /auth/callback?code=...&state=...
 *
 * Keycloak редиректит сюда после успешной аутентификации.
 *
 * 1. Проверяет state (CSRF protection)
 * 2. Извлекает code_verifier по state
 * 3. Обменивает code + code_verifier на токены (POST /token в Keycloak)
 * 4. Создаёт серверную сессию (session_id → tokens)
 * 5. Отдаёт фронтенду HttpOnly cookie и редиректит на главную
 */
public class CallbackHandler {

    private static final Logger log = LoggerFactory.getLogger(CallbackHandler.class);

    private final SessionStore sessionStore;
    private final KeycloakClient keycloakClient;

    public CallbackHandler(SessionStore sessionStore, KeycloakClient keycloakClient) {
        this.sessionStore = sessionStore;
        this.keycloakClient = keycloakClient;
    }

    public void handle(Context ctx) {
        var code = ctx.queryParam("code");
        var state = ctx.queryParam("state");
        var error = ctx.queryParam("error");

        // Keycloak вернул ошибку (пользователь отменил, или что-то пошло не так)
        if (error != null) {
            log.warn("Keycloak returned error: {} — {}", error, ctx.queryParam("error_description"));
            ctx.redirect(FRONTEND_URL + "?error=" + error);
            return;
        }

        // Проверяем наличие обязательных параметров
        if (code == null || state == null) {
            log.warn("Missing code or state in callback");
            ctx.status(400).result("Missing code or state");
            return;
        }

        // 1. Проверяем state и извлекаем code_verifier
        var codeVerifier = sessionStore.getAndRemoveState(state);
        if (codeVerifier == null) {
            log.warn("Invalid or expired state: {}...", state.substring(0, Math.min(8, state.length())));
            ctx.status(400).result("Invalid or expired state. Please try logging in again.");
            return;
        }

        // 2. Обмениваем code + code_verifier на токены
        var tokenResponse = keycloakClient.exchangeCode(code, codeVerifier, CALLBACK_URL);
        if (tokenResponse == null) {
            log.error("Token exchange failed");
            ctx.redirect(FRONTEND_URL + "?error=token_exchange_failed");
            return;
        }

        // 3. Создаём серверную сессию
        var sessionId = PkceUtil.generateSecureId();
        var userInfo = tokenResponse.userInfo();

        var sessionData = new SessionData(
                tokenResponse.accessToken(),
                tokenResponse.refreshToken(),
                userInfo.sub(),
                userInfo.username(),
                userInfo.email(),
                userInfo.roles(),
                Instant.now(),
                Instant.now(),
                tokenResponse.accessTokenExpiresAt()
        );

        sessionStore.put(sessionId, sessionData);

        // 4. Устанавливаем HttpOnly cookie и редиректим на фронтенд
        CookieUtil.setSessionCookie(ctx, sessionId, SESSION_TTL_SECONDS);

        log.info("Login successful: user={}, roles={} (session: {}...)",
                userInfo.username(), userInfo.roles(), sessionId.substring(0, 8));

        ctx.redirect(FRONTEND_URL);
    }
}
