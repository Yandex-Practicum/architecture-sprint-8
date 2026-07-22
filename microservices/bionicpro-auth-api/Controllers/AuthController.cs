using bionicpro_auth_api.Services;
using Microsoft.AspNetCore.Mvc;
using bionicpro_auth_api.Models;
using System.Text.Json;

namespace bionicpro_auth_api.Controllers;

[ApiController]
[Route("auth")]
public class AuthController(IKeycloakService keycloakService, ITokenStorage tokenStorage, IConfiguration configuration, IHttpClientFactory httpClientFactory, ILogger<AuthController> logger) : ControllerBase
{
    private readonly IKeycloakService _keycloakService = keycloakService;
    private readonly ITokenStorage _tokenStorage = tokenStorage;
    private readonly IConfiguration _configuration = configuration;
    private readonly IHttpClientFactory _httpClientFactory = httpClientFactory;
    private readonly ILogger<AuthController> _logger = logger;

    [HttpGet("login")]
    public IActionResult Login([FromQuery] string redirectUri = "/")
    {
        var state = Guid.NewGuid().ToString();
        HttpContext.Session.SetString("oauth_state", state);
        HttpContext.Session.SetString("redirect_uri", redirectUri);

        var authUrl = _keycloakService.GetAuthorizationUrl(state, redirectUri);

        return Redirect(authUrl);
    }

    [HttpGet("logout")]
    public async Task<IActionResult> Logout()
    {
        var sessionId = HttpContext.Session.Id;
        var tokens = await _tokenStorage.GetTokensAsync(sessionId);

        if (tokens != null && tokens.RefreshToken != null)
        {
            await _keycloakService.LogoutAsync(tokens.RefreshToken);
            await _tokenStorage.RemoveTokensAsync(sessionId);
        }

        HttpContext.Session.Clear();

        return Ok();
    }

    [HttpGet("callback")]
    public async Task<IActionResult> Callback([FromQuery] string code, [FromQuery] string state)
    {
        var savedState = HttpContext.Session.GetString("oauth_state");
        if (state != savedState)
        {
            return BadRequest("Invalid state parameter");
        }

        var redirectUri = HttpContext.Session.GetString("redirect_uri") ?? "/";
        var tokens = await _keycloakService.ExchangeCodeForTokensAsync(code,
            $"{Request.Scheme}://{Request.Host}/auth/callback");

        var sessionId = HttpContext.Session.Id;
        if (tokens != null)
            await _tokenStorage.StoreTokensAsync(sessionId, tokens);

        return Redirect(redirectUri);
    }

    [HttpGet("refresh")]
    public async Task<IActionResult> Refresh()
    {
        var sessionId = HttpContext.Session.Id;
        var tokens = await _tokenStorage.GetTokensAsync(sessionId);

        if (tokens == null)
        {
            return Unauthorized();
        }

        if (tokens != null && tokens.RefreshToken != null)
        {
            var newTokens = await _keycloakService.RefreshTokenAsync(tokens.RefreshToken);
            if (newTokens != null)
                await _tokenStorage.StoreTokensAsync(sessionId, newTokens);
        }

        return Ok();
    }

    [HttpGet("status")]
    public IActionResult Status()
    {
        return Ok(new { 
            status = "OK", 
            timestamp = DateTime.UtcNow
        });
    }

    [HttpGet("yandex/login")]
    public IActionResult YandexLogin()
    {
        var clientId = _configuration["Yandex:ClientId"];
        var redirectUri = _configuration["Yandex:RedirectUri"];
        
        var url = $"https://oauth.yandex.ru/authorize?" +
                  $"client_id={clientId}&" +
                  $"redirect_uri={redirectUri}&" +
                  $"response_type=code&" +
                  $"scope=login:email+login:info";
        
        return Redirect(url);
    }

    [HttpGet("yandex/callback")]
    public async Task<IActionResult> YandexCallback([FromQuery] string code)
    {
        if (string.IsNullOrEmpty(code))
        {
            return BadRequest("Missing code parameter");
        }

        try
        {
            var tokenResponse = await ExchangeCodeForYandexTokenAsync(code);
            if (tokenResponse == null)
            {
                return BadRequest("Failed to exchange code for token");
            }

            var userInfo = await GetYandexUserInfoAsync(tokenResponse.AccessToken);
            if (userInfo == null)
            {
                return BadRequest("Failed to get user info from Yandex");
            }

            var yandexUser = new YandexUser
            {
                Id = userInfo.Id,
                Email = userInfo.Email,
                FirstName = userInfo.FirstName,
                LastName = userInfo.LastName,
                AccessToken = tokenResponse.AccessToken,
                RefreshToken = tokenResponse.RefreshToken,
                ExpiresAt = DateTime.UtcNow.AddSeconds(tokenResponse.ExpiresIn)
            };

            await SaveYandexUserToRedisAsync(yandexUser);
            var sessionId = HttpContext.Session.Id;

            Response.Cookies.Append(".BionicPro.Session", sessionId, new CookieOptions
            {
                HttpOnly = true,
                Secure = false,
                SameSite = SameSiteMode.Lax,
                Expires = DateTimeOffset.UtcNow.AddMinutes(60)
            });

            var redirectUri = _configuration["Yandex:FrontendRedirectUri"] ?? "/";
            return Redirect(redirectUri);
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"Internal server error: {ex.Message}");
        }
    }

    private async Task<YandexTokenResponse> ExchangeCodeForYandexTokenAsync(string code)
    {
        var clientId = _configuration["Yandex:ClientId"];
        var clientSecret = _configuration["Yandex:ClientSecret"];
        var redirectUri = _configuration["Yandex:RedirectUri"];

        var client = _httpClientFactory.CreateClient();
        var parameters = new List<KeyValuePair<string, string>>
        {
            new("grant_type", "authorization_code"),
            new("code", code),
            new("client_id", clientId),
            new("client_secret", clientSecret),
            new("redirect_uri", redirectUri)
        };

        var response = await client.PostAsync("https://oauth.yandex.ru/token", new FormUrlEncodedContent(parameters));
        var responseBody = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
        {
            _logger.LogError("Yandex token error: {StatusCode}, {Body}", response.StatusCode, responseBody);
            return null;
        }

        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<YandexTokenResponse>(json);
    }

    [HttpGet("session")]
    public async Task<IActionResult> GetSession()
    {
        var sessionId = HttpContext.Session.Id;
        
        var tokens = await _tokenStorage.GetTokensAsync(sessionId);
        if (tokens != null)
        {
            return Ok(new { authenticated = true, source = "keycloak" });
        }
        
        var yandexTokens = await _tokenStorage.GetYandexTokensAsync(sessionId);
        if (yandexTokens != null)
        {
            return Ok(new { authenticated = true, source = "yandex" });
        }
        
        return Unauthorized(new { authenticated = false });
    }

    private async Task<YandexUserInfo> GetYandexUserInfoAsync(string accessToken)
    {
        var client = _httpClientFactory.CreateClient();
        client.DefaultRequestHeaders.Add("Authorization", $"OAuth {accessToken}");

        var response = await client.GetAsync("https://login.yandex.ru/info");
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        var data = JsonSerializer.Deserialize<JsonElement>(json);

        return new YandexUserInfo
        {
            Id = data.GetProperty("id").GetString(),
            Email = data.GetProperty("default_email").GetString(),
            FirstName = data.GetProperty("first_name").GetString(),
            LastName = data.GetProperty("last_name").GetString()
        };
    }

    private async Task SaveYandexUserToRedisAsync(YandexUser user)
    {
        var key = $"yandex_user:{user.Id}";
        var value = JsonSerializer.Serialize(user);

        await _tokenStorage.SaveYandexUserAsync(key, value);
    }
}