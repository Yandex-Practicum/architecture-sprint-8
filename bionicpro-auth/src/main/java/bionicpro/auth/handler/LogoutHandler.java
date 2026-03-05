package bionicpro.auth.handler;

import bionicpro.auth.keycloak.KeycloakClient;
import bionicpro.auth.session.SessionStore;
import bionicpro.auth.util.CookieUtil;
import io.javalin.http.Context;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

import static bionicpro.auth.AuthServer.*;

/**
 * POST /auth/logout
 *
 * 1. Извлекает session_id из куки
 * 2. Удаляет серверную сессию
 * 3. Очищает куку (Max-Age=0)
 * 4. Редиректит на Keycloak logout (SSO logout для всех клиентов)
 */
public class LogoutHandler {

    private static final Logger log = LoggerFactory.getLogger(LogoutHandler.class);

    private final SessionStore sessionStore;
    private final KeycloakClient keycloakClient;

    public LogoutHandler(SessionStore sessionStore, KeycloakClient keycloakClient) {
        this.sessionStore = sessionStore;
        this.keycloakClient = keycloakClient;
    }

    public void handle(Context ctx) {
        var sessionId = CookieUtil.getSessionId(ctx);

        if (sessionId != null) {
            sessionStore.remove(sessionId);
            log.info("Logout: session {}... removed", sessionId.substring(0, 8));
        }

        // Очищаем куку
        CookieUtil.clearSessionCookie(ctx);

        // Редирект на Keycloak logout (инвалидирует SSO-сессию)
        var logoutUrl = keycloakClient.getLogoutUrl()
                + "?post_logout_redirect_uri=" + URLEncoder.encode(FRONTEND_URL, StandardCharsets.UTF_8)
                + "&client_id=" + URLEncoder.encode(CLIENT_ID, StandardCharsets.UTF_8);

        ctx.redirect(logoutUrl);
    }
}
