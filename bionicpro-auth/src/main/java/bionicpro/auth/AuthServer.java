package bionicpro.auth;

import bionicpro.auth.handler.*;
import bionicpro.auth.keycloak.KeycloakClient;
import bionicpro.auth.session.InMemorySessionStore;
import bionicpro.auth.session.SessionStore;
import io.javalin.Javalin;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * BionicPRO Auth Service — Backend for Frontend (BFF).
 *
 * Реализует:
 * - PKCE flow с Keycloak
 * - Серверные сессии (токены никогда не попадают во фронтенд)
 * - HttpOnly cookie для аутентификации
 * - Ротацию session_id при каждом запросе (session fixation protection)
 * - Автоматический refresh access_token
 * - Проксирование запросов к downstream API с Bearer Token
 */
public class AuthServer {

    private static final Logger log = LoggerFactory.getLogger(AuthServer.class);

    // Конфигурация из переменных окружения (с дефолтами для локальной разработки)
    public static final String KEYCLOAK_URL = env("KEYCLOAK_URL", "http://localhost:8080");
    public static final String KEYCLOAK_EXTERNAL_URL = env("KEYCLOAK_EXTERNAL_URL", "http://localhost:8080");
    public static final String KEYCLOAK_REALM = env("KEYCLOAK_REALM", "reports-realm");
    public static final String CLIENT_ID = env("KEYCLOAK_CLIENT_ID", "reports-frontend");
    public static final String CLIENT_SECRET = env("KEYCLOAK_CLIENT_SECRET", "change-me-in-production");
    public static final String FRONTEND_URL = env("FRONTEND_URL", "http://localhost:3000");
    public static final String API_BASE_URL = env("API_BASE_URL", "http://localhost:8001");
    public static final String REPORT_SERVICE_URL = env("REPORT_SERVICE_URL", "http://localhost:8002");
    public static final String COOKIE_NAME = env("SESSION_COOKIE_NAME", "BIONIC_SESSION");
    public static final int PORT = Integer.parseInt(env("PORT", "8000"));
    public static final int SESSION_TTL_SECONDS = Integer.parseInt(env("SESSION_TTL_SECONDS", "1800")); // 30 min

    /** Callback URL — указывает на нас (BFF), НЕ на фронтенд! */
    public static final String CALLBACK_URL = env("CALLBACK_URL", "http://localhost:" + PORT + "/auth/callback");

    public static void main(String[] args) {
        var sessionStore = new InMemorySessionStore(SESSION_TTL_SECONDS);
        var keycloakClient = new KeycloakClient(KEYCLOAK_URL, KEYCLOAK_EXTERNAL_URL, KEYCLOAK_REALM, CLIENT_ID, CLIENT_SECRET);

        // Фоновая очистка истёкших сессий (каждые 5 минут)
        var scheduler = Executors.newSingleThreadScheduledExecutor(r -> {
            var t = new Thread(r, "session-cleanup");
            t.setDaemon(true);
            return t;
        });
        scheduler.scheduleAtFixedRate(sessionStore::cleanup, 5, 5, TimeUnit.MINUTES);

        // Handlers
        var loginHandler = new LoginHandler(sessionStore, keycloakClient);
        var callbackHandler = new CallbackHandler(sessionStore, keycloakClient);
        var logoutHandler = new LogoutHandler(sessionStore, keycloakClient);
        var proxyHandler = new ProxyHandler(sessionStore, keycloakClient);

        var app = Javalin.create(config -> {
            config.showJavalinBanner = false;
        }).start(PORT);

        // === Auth endpoints ===
        app.get("/auth/login", loginHandler::handle);
        app.get("/auth/callback", callbackHandler::handle);
        app.post("/auth/logout", logoutHandler::handle);

        // === Proxied API endpoints ===
        // Все запросы /api/* проксируются к downstream-сервисам с Bearer Token
        app.get("/api/**", proxyHandler::handle);
        app.post("/api/**", proxyHandler::handle);

        // === Health check ===
        app.get("/health", ctx -> ctx.json(java.util.Map.of(
                "status", "UP",
                "sessions", sessionStore.size()
        )));

        log.info("BionicPRO Auth (BFF) started on port {}", PORT);
        log.info("Keycloak: {}/realms/{}", KEYCLOAK_URL, KEYCLOAK_REALM);
        log.info("Frontend: {}", FRONTEND_URL);
        log.info("Callback: {}", CALLBACK_URL);
    }

    private static String env(String key, String defaultValue) {
        var value = System.getenv(key);
        return value != null ? value : defaultValue;
    }
}
