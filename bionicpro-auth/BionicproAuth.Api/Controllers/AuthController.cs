using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using BionicproAuth.Api.Crypto;
using BionicproAuth.Api.Model;
using BionicproAuth.Api.Services;
using BionicproAuth.Api.Session;
using Microsoft.AspNetCore.Mvc;

namespace BionicproAuth.Api.Controllers;

[ApiController]
[Route("auth")]
public class AuthController : ControllerBase
{
    private readonly ITokenService _tokenService;
    private readonly ISessionManager _sessionManager;
    private readonly IConfiguration _config;
    private readonly ILogger<AuthController> _logger;

    public AuthController(ITokenService tokenService, ISessionManager sessionManager, IConfiguration config, ILogger<AuthController> logger)
    {
        _tokenService = tokenService;
        _sessionManager = sessionManager;
        _config = config;
        _logger = logger;
    }

    // Эндпоинт для начала логина – редирект на Keycloak
    [HttpGet("login")]
    public IActionResult Login()
    {
        var authorizationEndpoint = $"{_config["Keycloak:Authority"]}/protocol/openid-connect/auth";
        var codeVerifier = CryptoRandom.CreateUniqueId(32); // генерируем PKCE code verifier
        var codeChallenge = CodeChallenge.GenerateCodeChallenge(codeVerifier, CodeChallengeMethod.S256);
        var state = Guid.NewGuid().ToString(); // для защиты от CSRF

        // Сохраняем codeVerifier и state в куки или временное хранилище (например, в сессию или кэш)
        Response.Cookies.Append("code_verifier", codeVerifier, new CookieOptions
        {
            HttpOnly = true,
            Secure = true,
            MaxAge = TimeSpan.FromMinutes(5),
            SameSite = SameSiteMode.Lax
        });
        Response.Cookies.Append("auth_state", state, new CookieOptions
        {
            HttpOnly = true,
            Secure = true,
            MaxAge = TimeSpan.FromMinutes(5),
            SameSite = SameSiteMode.Lax
        });

        var redirectUrl = $"{authorizationEndpoint}?" +
            $"client_id={_config["Keycloak:ClientId"]}&" +
            $"redirect_uri={Uri.EscapeDataString(_config["Keycloak:RedirectUri"])}&" +
            $"response_type=code&" +
            $"scope=openid profile email&" +
            $"state={state}&" +
            $"code_challenge={codeChallenge}&" +
            $"code_challenge_method=S256";

        return Redirect(redirectUrl);
    }

    // Эндпоинт обратного вызова от Keycloak
    [HttpGet("callback")]
    public async Task<IActionResult> Callback([FromQuery] string code, [FromQuery] string? state,[FromQuery] string? session_state=null)
    {
        // Проверяем state
        if (!Request.Cookies.TryGetValue("auth_state", out var savedState) || savedState != state)
        {
            return BadRequest("Invalid state parameter");
        }

        if (!Request.Cookies.TryGetValue("code_verifier", out var codeVerifier))
        {
            return BadRequest("Missing code verifier");
        }

        try
        {
            // Обмениваем код на токены
            var tokens = await _tokenService.ExchangeCodeForTokensAsync(code, codeVerifier);

            // Декодируем ID token, чтобы получить информацию о пользователе
            var handler = new JwtSecurityTokenHandler();
            var idToken = handler.ReadJwtToken(tokens.IdToken);
            var userId = idToken.Subject;
            var claims = idToken.Claims;
            _logger.LogError( "AccessToken:{AccessToken}", tokens.AccessToken);

            // Создаём сессию
            var sessionId = _sessionManager.CreateSession(tokens, userId, claims);

            // Устанавливаем cookie сессии (HttpOnly, Secure)
            Response.Cookies.Append(_config["Session:CookieName"], sessionId, new CookieOptions
            {
                HttpOnly = true,
                Secure = true,
                SameSite = SameSiteMode.Lax,
                MaxAge = TimeSpan.FromMinutes(_config.GetValue<int>("Session:SessionLifetimeMinutes")),
                Domain = _config["Session:CookieDomain"]
            });

            // Очищаем временные куки
            Response.Cookies.Delete("auth_state");
            Response.Cookies.Delete("code_verifier");

            // Редирект на фронтенд
            return Redirect(_config["Keycloak:PostLogoutRedirectUri"]);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during token exchange");
            return BadRequest("Authentication failed");
        }
    }

    
   

    // Эндпоинт для выхода
    [HttpPost("logout")]
    public IActionResult Logout()
    {
        var sessionId = Request.Cookies[_config["Session:CookieName"]];
        if (!string.IsNullOrEmpty(sessionId))
        {
            _sessionManager.RemoveSession(sessionId);
            Response.Cookies.Delete(_config["Session:CookieName"]);
        }

        // Редирект на logout Keycloak (опционально)
        var logoutUrl = $"{_config["Keycloak:Authority"]}/protocol/openid-connect/logout?" +
            $"post_logout_redirect_uri={Uri.EscapeDataString(_config["Keycloak:PostLogoutRedirectUri"])}";
        return Redirect(logoutUrl);
    }

    // Эндпоинт для проверки сессии (используется фронтендом)
    [HttpGet("me")]
    public IActionResult GetCurrentUser()
    {
        var session = HttpContext.Items["Session"] as SessionData;
        if (session == null)
            return Unauthorized();

        return Ok(new
        {
            session.UserId,
            Claims = session.Claims
        });
    }
    
    [HttpGet("login/yandex")]
    public IActionResult LoginWithYandex()
    {
       // var authorizationEndpoint = $"{_config["Keycloak:Authority"]}/protocol/openid-connect/auth";
        var codeVerifier = CryptoRandom.CreateUniqueId(32); // генерируем PKCE code verifier
        var codeChallenge = CodeChallenge.GenerateCodeChallenge(codeVerifier, CodeChallengeMethod.S256);
        var state = Guid.NewGuid().ToString(); // для защиты от CSRF
        
        
        // Используем параметр kc_idp_hint для автоматического редиректа на Яндекс [citation:8]
        var keycloakAuthUrl = $"{_config["Keycloak:Authority"]}/protocol/openid-connect/auth?" +
                              $"client_id={_config["Keycloak:ClientId"]}&" +
                              $"response_type=code&" +
                              $"scope=openid profile email&" +
                              $"redirect_uri={Uri.EscapeDataString(_config["Keycloak:RedirectUri"])}&" +
                              $"kc_idp_hint=yandex&" + 
                              $"state={state}&" +
                              $"code_challenge={codeChallenge}&" +
                              $"code_challenge_method=S256";
        
        Response.Cookies.Append("auth_state", state, new CookieOptions
        {
            HttpOnly = true,
            Secure = true,
            MaxAge = TimeSpan.FromMinutes(5),
            SameSite = SameSiteMode.Lax
        });
        
        Response.Cookies.Append("code_verifier", codeVerifier, new CookieOptions
        {
            HttpOnly = true,
            Secure = true,
            MaxAge = TimeSpan.FromMinutes(5),
            SameSite = SameSiteMode.Lax
        });
        

        return Redirect(keycloakAuthUrl);
    }
}