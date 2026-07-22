namespace bionicpro_auth_api.Middleware;
using bionicpro_auth_api.Services;

public class SessionRotationMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<SessionRotationMiddleware> _logger;

    public SessionRotationMiddleware(RequestDelegate next, ILogger<SessionRotationMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context, ITokenStorage tokenStorage)
    {
        if (context.Request.Path.StartsWithSegments("/auth"))
        {
            await _next(context);
            return;
        }

        var oldSessionId = context.Session.Id;
        
        var tokens = await tokenStorage.GetTokensAsync(oldSessionId);
        
        if (tokens != null)
        {
            context.Session.Clear();
            var newSessionId = context.Session.Id;
            
            await tokenStorage.StoreTokensAsync(newSessionId, tokens);
            await tokenStorage.RemoveTokensAsync(oldSessionId);
            
            context.Response.Cookies.Append(
                ".BionicPro.Session",
                newSessionId,
                new CookieOptions
                {
                    HttpOnly = true,
                    Secure = true,
                    SameSite = SameSiteMode.Lax,
                    Expires = DateTimeOffset.UtcNow.AddMinutes(60)
                }
            );
        }

        await _next(context);
    }
}