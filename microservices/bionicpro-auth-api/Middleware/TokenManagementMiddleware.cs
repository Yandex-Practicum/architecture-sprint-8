using bionicpro_auth_api.Services;
using System.IdentityModel.Tokens.Jwt;

namespace bionicpro_auth_api.Middleware;

public class TokenManagementMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<TokenManagementMiddleware> _logger;

    public TokenManagementMiddleware(RequestDelegate next, ILogger<TokenManagementMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context, ITokenStorage tokenStorage, IKeycloakService keycloakService)
    {
        if (context.Request.Path.StartsWithSegments("/auth"))
        {
            await _next(context);
            return;
        }

        var sessionId = context.Session.Id;
        var tokens = await tokenStorage.GetTokensAsync(sessionId);

        if (tokens != null)
        {
            if (IsTokenExpired(tokens.AccessToken))
            {
                try
                {
                    if (tokens.RefreshToken is not null)
                    {
                        var newTokens = await keycloakService.RefreshTokenAsync(tokens.RefreshToken);
                        if(newTokens is not null)
                            await tokenStorage.StoreTokensAsync(sessionId, newTokens);
                        tokens = newTokens;
                    }
                }
                catch (Exception ex)
                {
                    await tokenStorage.RemoveTokensAsync(sessionId);
                    context.Response.StatusCode = StatusCodes.Status401Unauthorized;
                    return;
                }
            }

            context.Request.Headers["Authorization"] = $"Bearer {tokens?.AccessToken ?? string.Empty}";
            context.Request.Headers["X-User-ID"] = GetUserIdFromToken(tokens?.AccessToken ?? string.Empty);
        }

        await _next(context);
    }

    private static bool IsTokenExpired(string token)
    {
        try
        {
            var handler = new JwtSecurityTokenHandler();
            var jwt = handler.ReadJwtToken(token);
            
            return jwt.ValidTo < DateTime.UtcNow.AddSeconds(30); 
        }
        catch
        {
            return true;
        }
    }


    private static string GetUserIdFromToken(string token)
    {
        var handler = new JwtSecurityTokenHandler();
        var jwt = handler.ReadJwtToken(token);

        return jwt.Subject;
    }
}