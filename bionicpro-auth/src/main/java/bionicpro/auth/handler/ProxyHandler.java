package bionicpro.auth.handler;

import bionicpro.auth.keycloak.KeycloakClient;
import bionicpro.auth.session.SessionData;
import bionicpro.auth.session.SessionStore;
import bionicpro.auth.util.CookieUtil;
import bionicpro.auth.util.PkceUtil;
import io.javalin.http.Context;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import static bionicpro.auth.AuthServer.*;

/**
 * GET/POST /api/**
 *
 * Центральный handler BFF. При каждом запросе:
 *
 * 1. Извлекает session_id из куки
 * 2. Атомарно получает и удаляет сессию (getAndRemove)
 * 3. Если access_token истёк — обновляет через refresh_token
 * 4. Генерирует новый session_id (ротация — session fixation protection)
 * 5. Сохраняет сессию под новым session_id
 * 6. Проксирует запрос к downstream API с Authorization: Bearer <token>
 * 7. Возвращает ответ клиенту с обновлённой кукой
 */
public class ProxyHandler {

    private static final Logger log = LoggerFactory.getLogger(ProxyHandler.class);

    private final SessionStore sessionStore;
    private final KeycloakClient keycloakClient;
    private final HttpClient httpClient;

    public ProxyHandler(SessionStore sessionStore, KeycloakClient keycloakClient) {
        this.sessionStore = sessionStore;
        this.keycloakClient = keycloakClient;
        this.httpClient = HttpClient.newHttpClient();
    }

    public void handle(Context ctx) {
        // 1. Извлекаем session_id
        var sessionId = CookieUtil.getSessionId(ctx);
        if (sessionId == null) {
            log.debug("No session cookie, returning 401");
            ctx.status(401).json(errorJson("Not authenticated. Please login."));
            return;
        }

        // 2. Атомарно получаем и удаляем старую сессию
        var sessionData = sessionStore.getAndRemove(sessionId);
        if (sessionData == null) {
            log.debug("Session not found or expired: {}...", sessionId.substring(0, 8));
            CookieUtil.clearSessionCookie(ctx);
            ctx.status(401).json(errorJson("Session expired. Please login again."));
            return;
        }

        // 3. Refresh access_token если истёк
        if (sessionData.isAccessTokenExpired()) {
            log.debug("Access token expired for user {}, refreshing", sessionData.username());
            var tokenResponse = keycloakClient.refresh(sessionData.refreshToken());

            if (tokenResponse == null) {
                // refresh_token тоже истёк → нужен повторный логин
                log.info("Refresh failed for user {} — session terminated", sessionData.username());
                CookieUtil.clearSessionCookie(ctx);
                ctx.status(401).json(errorJson("Session expired. Please login again."));
                return;
            }

            sessionData = sessionData.withTokens(
                    tokenResponse.accessToken(),
                    tokenResponse.refreshToken(),
                    tokenResponse.accessTokenExpiresAt()
            );
            log.debug("Token refreshed for user {}", sessionData.username());
        }

        // 4. Ротация: новый session_id
        var newSessionId = PkceUtil.generateSecureId();
        sessionData = sessionData.touch();
        sessionStore.put(newSessionId, sessionData);

        // 5. Обновляем куку
        CookieUtil.setSessionCookie(ctx, newSessionId, SESSION_TTL_SECONDS);

        // 6. Проксируем к downstream API
        proxyRequest(ctx, sessionData);
    }

    private void proxyRequest(Context ctx, SessionData session) {
        // Определяем downstream URL
        var path = ctx.path();  // например, /api/reports/me
        // Report Service слушает /reports/*, не /api/reports/*
        // Убираем /api prefix при проксировании
        var downstreamPath = path.startsWith("/api") ? path.substring(4) : path;
        var downstreamBase = path.startsWith("/api/reports") ? REPORT_SERVICE_URL : API_BASE_URL;
        var downstreamUrl = downstreamBase + downstreamPath;

        // Добавляем query string если есть
        var queryString = ctx.queryString();
        if (queryString != null && !queryString.isEmpty()) {
            downstreamUrl += "?" + queryString;
        }

        try {
            // Строим запрос к downstream
            var requestBuilder = HttpRequest.newBuilder()
                    .uri(URI.create(downstreamUrl))
                    .header("Authorization", "Bearer " + session.accessToken())
                    .header("X-User-Id", session.userId())
                    .header("X-User-Roles", session.roles())
                    // DEMO: извлекаем числовой CRM ID из username (prothetic1 → 1).
                    // В проде → Keycloak user attribute + protocol mapper → claim crm_user_id в JWT.
                    .header("X-CRM-User-Id", extractCrmUserId(session.username()));

            // Проксируем метод и тело
            if ("POST".equalsIgnoreCase(ctx.method().name()) && ctx.body() != null) {
                requestBuilder.POST(HttpRequest.BodyPublishers.ofString(ctx.body()));
                requestBuilder.header("Content-Type",
                        ctx.contentType() != null ? ctx.contentType() : "application/json");
            } else {
                requestBuilder.GET();
            }

            var response = httpClient.send(requestBuilder.build(), HttpResponse.BodyHandlers.ofString());

            // Проксируем ответ
            ctx.status(response.statusCode());
            response.headers().firstValue("Content-Type")
                    .ifPresent(ct -> ctx.contentType(ct));
            ctx.result(response.body());

            log.debug("Proxied {} {} → {} (status: {})",
                    ctx.method(), path, downstreamUrl, response.statusCode());

        } catch (Exception e) {
            log.error("Proxy error: {} {} → {}", ctx.method(), path, downstreamUrl, e);
            ctx.status(502).json(errorJson("Downstream service unavailable"));
        }
    }

    private java.util.Map<String, String> errorJson(String message) {
        return java.util.Map.of("error", message);
    }

    /**
     * Извлекает числовой CRM user ID из Keycloak username.
     * Пример: "prothetic1" → "1", "user42" → "42".
     *
     * DEMO-решение. В production-среде CRM ID должен быть claim в JWT
     * (через Keycloak User Attribute + Protocol Mapper).
     */
    private static String extractCrmUserId(String username) {
        if (username == null) return "0";
        var m = java.util.regex.Pattern.compile("(\\d+)$").matcher(username);
        return m.find() ? m.group(1) : "0";
    }

}
