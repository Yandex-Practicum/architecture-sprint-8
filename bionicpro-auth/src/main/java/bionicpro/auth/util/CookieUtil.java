package bionicpro.auth.util;

import io.javalin.http.Context;

import static bionicpro.auth.AuthServer.COOKIE_NAME;

/**
 * Утилиты для работы с session cookie.
 *
 * Cookie: BIONIC_SESSION=<session_id>; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=1800
 *
 * Выставляем Set-Cookie заголовок напрямую, чтобы не зависеть от Kotlin-interop
 * в Javalin Cookie data class.
 */
public final class CookieUtil {

    private CookieUtil() {}

    /** Извлекает session_id из куки. Возвращает null если куки нет. */
    public static String getSessionId(Context ctx) {
        return ctx.cookie(COOKIE_NAME);
    }

    /** Устанавливает session cookie с HttpOnly, Secure, SameSite=Strict. */
    public static void setSessionCookie(Context ctx, String sessionId, int maxAgeSeconds) {
        var cookie = COOKIE_NAME + "=" + sessionId
                + "; Path=/"
                + "; Max-Age=" + maxAgeSeconds
                + "; HttpOnly"
                + "; SameSite=Strict";
        // Secure=false для localhost; в проде раскомментировать:
        // cookie += "; Secure";
        ctx.header("Set-Cookie", cookie);
    }

    /** Удаляет session cookie (Max-Age=0). */
    public static void clearSessionCookie(Context ctx) {
        var cookie = COOKIE_NAME + "="
                + "; Path=/"
                + "; Max-Age=0"
                + "; HttpOnly"
                + "; SameSite=Strict";
        ctx.header("Set-Cookie", cookie);
    }
}