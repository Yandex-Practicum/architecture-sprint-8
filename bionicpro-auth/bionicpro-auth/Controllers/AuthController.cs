// Controllers/AuthController.cs
using bionicpro_auth.Components.Handlers;
using bionicpro_auth.Components.Handlers.Implementation;
using bionicpro_auth.Models;
using bionicpro_auth.Models.Settings;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Options;
using System.Runtime;
using System.Security.Cryptography;
using System.Text;

namespace BionicProAuth.Controllers;

[ApiController]
[Route("api/auth")]
public class AuthController : ControllerBase
{
    private readonly IKeyCloakService _keycloakService;
    private readonly ISessionService _sessionService;
    private readonly IMemoryCache _cache;
    private readonly IOptionsMonitor<AppSettings> _settings;
    private readonly ILogger<AuthController> _logger;

    public AuthController(
        IKeyCloakService keycloakService,
        IMemoryCache cache,
        ISessionService sessionService,
        IOptionsMonitor<AppSettings> settings,
        ILogger<AuthController> logger)
    {
        _settings = settings;
        _keycloakService = keycloakService;
        _sessionService = sessionService;
        _cache = cache;
        _logger = logger;
    }

    /// <summary>
    /// Начало авторизации - возвращает URL для редиректа на Keycloak
    /// </summary>
    [HttpGet("login-url")]
    public IActionResult GetLoginUrl([FromQuery] string? idpHint = null)
    {
        var codeVerifier = GenerateCodeVerifier();
        var codeChallenge = GenerateCodeChallenge(codeVerifier);
        var state = Guid.NewGuid().ToString();
        var redirectUri = $"{Request.Scheme}://{Request.Host}/api/auth/callback";

        // Сохраняем state для проверки
        _cache.Set($"oauth_state_{state}", codeVerifier, TimeSpan.FromMinutes(10));

        var authUrl = _keycloakService.GenerateAuthorizationUrl(state, codeChallenge, redirectUri, idpHint);

        return Ok(new { url = authUrl });
    }

    /// <summary>
    /// Callback после авторизации в Keycloak
    /// Keycloak уже проверил пароль и OTP (если включен)
    /// </summary>
    [HttpGet("callback")]
    public async Task<IActionResult> Callback([FromQuery] string code, [FromQuery] string state, [FromQuery] string? error)
    {
        if (!string.IsNullOrEmpty(error))
        {
            _logger.LogError($"OAuth error: {error}");
            return Redirect($"{GetFrontendUrl()}/login?error={error}");
        }

        // Проверяем state
        if (!_cache.TryGetValue($"oauth_state_{state}", out _))
        {
            return BadRequest("Invalid state");
        }

        var redirectUri = $"{Request.Scheme}://{Request.Host}/api/auth/callback";

        // Обмениваем code на токены
        var tokens = await _keycloakService.ExchangeCodeForTokensAsync(code, redirectUri);

        if (tokens == null)
        {
            return Redirect($"{GetFrontendUrl()}/login?error=token_exchange_failed");
        }

        // Получаем информацию о пользователе
        var userInfo = await _keycloakService.GetUserInfoAsync(tokens.Tokens!.AccessToken);

        SessionData session = _sessionService.CreateSession(userInfo, tokens.Tokens);

        // Создаем cookie
        Response.Cookies.Append("session_id", session.SessionId.ToString(), new CookieOptions
        {
            HttpOnly = true,
            Secure = true,
            SameSite = SameSiteMode.Strict,
            MaxAge = TimeSpan.FromMinutes(15),
            Path = "/"
        });

        // Редирект на фронтенд
        return Redirect($"{GetFrontendUrl()}/auth/callback?success=true");
    }

    /// <summary>
    /// Проверка сессии
    /// </summary>
    [HttpGet("session")]
    public IActionResult GetSession()
    {
        var sessionId = HttpContext.Items["Session"] as Guid?;

        if (sessionId is null)
        {
            return Unauthorized();
        }

        SessionData session = _sessionService.GetSession(sessionId!.Value);

        return Ok(new
        {
            authenticated = true,
            username = session!.UserInfo.PreferredUsername,
            email = session.UserInfo.Email
        });
    }

    /// <summary>
    /// Выход
    /// </summary>
    [HttpPost("logout")]
    public IActionResult Logout()
    {
        var sessionId = Request.Cookies["session_id"];
        if (!string.IsNullOrEmpty(sessionId))
        {
            _cache.Remove($"session_{sessionId}");
            Response.Cookies.Delete("session_id");
        }

        return Ok(new { success = true });
    }

    private string GetFrontendUrl()
    {
        return _settings.CurrentValue.Frontend;
    }



    private string GenerateCodeVerifier()
    {
        var randomBytes = new byte[32];
        using (var rng = RandomNumberGenerator.Create())
        {
            rng.GetBytes(randomBytes);
        }
        return Convert.ToBase64String(randomBytes)
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');
    }

    private string GenerateCodeChallenge(string codeVerifier)
    {
        using (var sha256 = SHA256.Create())
        {
            var hash = sha256.ComputeHash(Encoding.UTF8.GetBytes(codeVerifier));
            return Convert.ToBase64String(hash)
                .TrimEnd('=')
                .Replace('+', '-')
                .Replace('/', '_');
        }
    }
}
