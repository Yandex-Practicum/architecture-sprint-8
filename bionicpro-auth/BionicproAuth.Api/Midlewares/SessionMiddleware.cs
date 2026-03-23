using BionicproAuth.Api.Services;
using BionicproAuth.Api.Session;

namespace BionicproAuth.Api.Midlewares;

public class SessionMiddleware
{
    private readonly RequestDelegate _next;
    private readonly IConfiguration _config;

    public SessionMiddleware(RequestDelegate next, IConfiguration config)
    {
        _next = next;
        _config = config;
    }

    public async Task InvokeAsync(HttpContext context, ISessionManager sessionManager, ITokenService tokenService)
    {
        var sessionCookieName = _config["Session:CookieName"];
        if (context.Request.Cookies.TryGetValue(sessionCookieName, out var sessionId))
        {
            var session = sessionManager.GetSession(sessionId);
            if (session != null)
            {
                // Проверяем, не истёк ли access token
                if (session.AccessTokenExpiresAt <= DateTime.UtcNow)
                {
                    // Пытаемся обновить токены
                    try
                    {
                        // Расшифровываем refresh token (нужно реализовать метод расшифровки)
                        var refreshToken = UnprotectRefreshToken(session.RefreshToken); 
                        var newTokens = await tokenService.RefreshAccessTokenAsync(refreshToken);
                        sessionManager.UpdateSession(sessionId, newTokens);
                        session = sessionManager.GetSession(sessionId); // обновлённые данные
                    }
                    catch (Exception ex)
                    {
                        // Если обновить не удалось – удаляем сессию
                        sessionManager.RemoveSession(sessionId);
                        context.Response.Cookies.Delete(sessionCookieName);
                        context.Response.StatusCode = StatusCodes.Status401Unauthorized;
                        return;
                    }
                }

                // Ротация сессии: создаём новый sessionId, обновляем cookie
                session = sessionManager.RotateSession(sessionId, out var newSessionId);
                if (!string.IsNullOrEmpty(newSessionId))
                {
                    context.Response.Cookies.Append(sessionCookieName, newSessionId, new CookieOptions
                    {
                        HttpOnly = true,
                        Secure = true,
                        SameSite = SameSiteMode.Lax,
                        MaxAge = TimeSpan.FromMinutes(_config.GetValue<int>("Session:SessionLifetimeMinutes")),
                        Domain = _config["Session:CookieDomain"]
                    });
                }

                // Добавляем информацию о пользователе в контекст для дальнейшего использования
                context.Items["Session"] = session;
                context.Items["UserId"] = session.UserId;
                context.Items["AccessToken"] = session.AccessToken;
            }
            else
            {
                // Сессия не найдена – удаляем cookie
                context.Response.Cookies.Delete(sessionCookieName);
            }
        }

        await _next(context);
    }

    private string UnprotectRefreshToken(string protectedToken)
    {
        // Здесь должна быть расшифровка с использованием IDataProtector
        // Но для простоты можно хранить в открытом виде, если сервер в защищённой среде.
        // В реальном проекте используйте внедрённый protector.
        return protectedToken; // упрощение
    }
}