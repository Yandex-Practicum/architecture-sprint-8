package bionicpro.auth.handler;

import bionicpro.auth.keycloak.KeycloakClient;
import bionicpro.auth.session.SessionStore;
import bionicpro.auth.util.PkceUtil;
import io.javalin.http.Context;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

import static bionicpro.auth.AuthServer.*;

/**
 * GET /auth/login
 *
 * 1. Генерирует PKCE (code_verifier + code_challenge)
 * 2. Генерирует state (CSRF protection)
 * 3. Сохраняет code_verifier привязанным к state
 * 4. Редиректит пользователя на Keycloak Authorization Endpoint
 */
public class LoginHandler {

    private static final Logger log = LoggerFactory.getLogger(LoginHandler.class);

    private final SessionStore sessionStore;
    private final KeycloakClient keycloakClient;

    public LoginHandler(SessionStore sessionStore, KeycloakClient keycloakClient) {
        this.sessionStore = sessionStore;
        this.keycloakClient = keycloakClient;
    }

    public void handle(Context ctx) {
        // 1. Генерируем PKCE
        var codeVerifier = PkceUtil.generateCodeVerifier();
        var codeChallenge = PkceUtil.generateCodeChallenge(codeVerifier);

        // 2. Генерируем state
        var state = PkceUtil.generateSecureId();

        // 3. Сохраняем verifier (серверная сторона, фронтенд его не видит)
        sessionStore.putState(state, codeVerifier);

        // 4. Строим URL для Keycloak
        var authUrl = keycloakClient.getAuthUrl()
                + "?response_type=code"
                + "&client_id=" + encode(CLIENT_ID)
                + "&redirect_uri=" + encode(CALLBACK_URL)
                + "&scope=openid"
                + "&state=" + encode(state)
                + "&code_challenge=" + encode(codeChallenge)
                + "&code_challenge_method=S256";

        log.info("Login initiated, redirecting to Keycloak (state: {}...)", state.substring(0, 8));
        ctx.redirect(authUrl);
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }
}
