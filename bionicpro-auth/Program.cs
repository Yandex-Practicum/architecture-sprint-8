// bionicpro-auth — BFF (Backend for Frontend)
// Реализует: PKCE flow, хранение токенов в памяти, HttpOnly session cookie,
//            ротацию session_id (защита от Session Fixation), обновление access_token.
//
// Концепция BFF: браузер никогда не видит access_token / refresh_token.
// Он получает только session cookie. Все токены живут в памяти этого сервиса.

using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddCors(options =>
{
    options.AddPolicy("frontend", policy =>
        policy.WithOrigins(builder.Configuration["Frontend:Url"] ?? "http://localhost:3000")
              .AllowAnyHeader()
              .AllowAnyMethod()
              .AllowCredentials());
});

var app = builder.Build();
app.UseCors("frontend");

// ─── Конфигурация ───────────────────────────────────────────────────────────
var keycloakUrl   = builder.Configuration["Keycloak:Url"]      ?? "http://keycloak:8080";
var realm         = builder.Configuration["Keycloak:Realm"]    ?? "reports-realm";
var clientId      = builder.Configuration["Keycloak:ClientId"] ?? "bionicpro-auth";
var clientSecret  = builder.Configuration["Keycloak:Secret"]   ?? "";
var redirectUri   = builder.Configuration["Keycloak:RedirectUri"] ?? "http://localhost:8001/auth/callback";
var frontendUrl   = builder.Configuration["Frontend:Url"]      ?? "http://localhost:3000";
var reportApiUrl  = builder.Configuration["ReportApi:Url"]     ?? "http://report-api:8080";

var tokenUrl      = $"{keycloakUrl}/realms/{realm}/protocol/openid-connect/token";
var authUrl       = $"{keycloakUrl}/realms/{realm}/protocol/openid-connect/auth";

int accessTokenTtlSeconds  = 120;   // access_token живёт 2 минуты
int sessionTtlSeconds      = 3600;  // сессия живёт 1 час

// ─── Хранилища в памяти ─────────────────────────────────────────────────────

// session_id → данные сессии
var sessions = new ConcurrentDictionary<string, SessionData>();

// state (OAuth nonce) → code_verifier для PKCE
var pkceStates = new ConcurrentDictionary<string, string>();

// ─── Вспомогательные функции ─────────────────────────────────────────────────

// Генерация code_verifier: 32 случайных байта → Base64URL (43 символа)
static string GenerateCodeVerifier()
{
    var bytes = RandomNumberGenerator.GetBytes(32);
    return Base64UrlEncode(bytes);
}

// code_challenge = BASE64URL(SHA256(code_verifier))
// Это ключевая идея PKCE: если перехватят AUTH_CODE — без verifier он бесполезен
static string GenerateCodeChallenge(string verifier)
{
    var hash = SHA256.HashData(Encoding.ASCII.GetBytes(verifier));
    return Base64UrlEncode(hash);
}

static string Base64UrlEncode(byte[] bytes) =>
    Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');

static string NewSessionId() =>
    Base64UrlEncode(RandomNumberGenerator.GetBytes(32));

// Достать user_id и username из JWT payload (без верификации подписи —
// подпись уже проверена Keycloak, доверяем внутренней сети)
static (string UserId, string Username) ParseJwtPayload(string jwt)
{
    var parts = jwt.Split('.');
    if (parts.Length < 2) return ("", "");
    var padding = (4 - parts[1].Length % 4) % 4;
    var base64  = parts[1].Replace('-', '+').Replace('_', '/') + new string('=', padding);
    var json    = Encoding.UTF8.GetString(Convert.FromBase64String(base64));
    using var doc = JsonDocument.Parse(json);
    var sub  = doc.RootElement.TryGetProperty("sub",                  out var s) ? s.GetString() ?? "" : "";
    var name = doc.RootElement.TryGetProperty("preferred_username",   out var n) ? n.GetString() ?? "" : "";
    return (sub, name);
}

// ─── Эндпоинты ───────────────────────────────────────────────────────────────

// 1. Инициирует PKCE-логин: генерирует verifier, challenge, редиректит в Keycloak
app.MapGet("/auth/login", (HttpResponse response) =>
{
    var state         = NewSessionId();
    var codeVerifier  = GenerateCodeVerifier();
    var codeChallenge = GenerateCodeChallenge(codeVerifier);

    pkceStates[state] = codeVerifier;   // сохраняем verifier по state

    // Строим URL для Keycloak
    var query = new Dictionary<string, string>
    {
        ["response_type"]          = "code",
        ["client_id"]              = clientId,
        ["redirect_uri"]           = redirectUri,
        ["scope"]                  = "openid profile email",
        ["state"]                  = state,
        ["code_challenge"]         = codeChallenge,
        ["code_challenge_method"]  = "S256",
    };
    var qs = string.Join("&", query.Select(kv =>
        $"{Uri.EscapeDataString(kv.Key)}={Uri.EscapeDataString(kv.Value)}"));

    return Results.Redirect($"{authUrl}?{qs}");
});

// 2. Callback от Keycloak: обменивает AUTH_CODE + code_verifier на токены,
//    сохраняет их в памяти, выдаёт session cookie
app.MapGet("/auth/callback", async (string code, string state, HttpResponse response) =>
{
    if (!pkceStates.TryRemove(state, out var codeVerifier))
        return Results.BadRequest("Invalid state");

    // Обмен кода на токены — сервер-сервер, браузер не участвует
    using var http = new HttpClient();
    var form = new Dictionary<string, string>
    {
        ["grant_type"]    = "authorization_code",
        ["code"]          = code,
        ["redirect_uri"]  = redirectUri,
        ["client_id"]     = clientId,
        ["code_verifier"] = codeVerifier,   // PKCE: сервер присылает verifier
    };
    if (!string.IsNullOrEmpty(clientSecret))
        form["client_secret"] = clientSecret;

    var tokenResponse = await http.PostAsync(tokenUrl, new FormUrlEncodedContent(form));
    if (!tokenResponse.IsSuccessStatusCode)
        return Results.Problem("Token exchange failed");

    var tokenJson    = await tokenResponse.Content.ReadAsStringAsync();
    using var doc    = JsonDocument.Parse(tokenJson);
    var accessToken  = doc.RootElement.GetProperty("access_token").GetString()!;
    var refreshToken = doc.RootElement.TryGetProperty("refresh_token", out var rt) ? rt.GetString()! : "";

    var (userId, username) = ParseJwtPayload(accessToken);

    var sessionId = NewSessionId();
    sessions[sessionId] = new SessionData
    {
        AccessToken   = accessToken,
        RefreshToken  = refreshToken,
        TokenExpiry   = DateTime.UtcNow.AddSeconds(accessTokenTtlSeconds),
        SessionExpiry = DateTime.UtcNow.AddSeconds(sessionTtlSeconds),
        UserId        = userId,
        Username      = username,
    };

    // Ключевой момент: HttpOnly = true → JS в браузере cookie не видит
    response.Cookies.Append("session", sessionId, new CookieOptions
    {
        HttpOnly = true,
        Secure   = false,   // true в продакшене (HTTPS)
        SameSite = SameSiteMode.Lax,
        MaxAge   = TimeSpan.FromSeconds(sessionTtlSeconds),
    });

    return Results.Redirect(frontendUrl);
});

// 3. Logout
app.MapGet("/auth/logout", (HttpRequest request, HttpResponse response) =>
{
    if (request.Cookies.TryGetValue("session", out var sessionId))
        sessions.TryRemove(sessionId, out _);

    response.Cookies.Delete("session");
    return Results.Redirect(frontendUrl);
});

// 4. Userinfo — кто залогинен
app.MapGet("/auth/userinfo", (HttpRequest request, HttpResponse response) =>
{
    if (!TryGetValidSession(request, out var sess, out var oldId))
        return Results.Unauthorized();

    RotateSession(oldId!, sess!, response);
    return Results.Ok(new { sess!.UserId, sess.Username });
});

// 5. Прокси к Report API с автоматическим refresh токена
app.MapGet("/api/reports", async (HttpRequest request, HttpResponse response) =>
{
    if (!TryGetValidSession(request, out var sess, out var oldId))
        return Results.Unauthorized();

    // Если access_token протух — обновляем через refresh_token
    if (DateTime.UtcNow >= sess!.TokenExpiry)
    {
        var refreshed = await RefreshTokenAsync(sess);
        if (!refreshed) return Results.Unauthorized();
    }

    // Ротация session_id при каждом запросе (Session Fixation Prevention)
    var newId = RotateSession(oldId!, sess, response);

    // Форвардим запрос к Report API с Bearer токеном
    using var http = new HttpClient();
    http.DefaultRequestHeaders.Authorization =
        new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", sess.AccessToken);

    var apiResponse = await http.GetAsync($"{reportApiUrl}/reports?user_id={sess.UserId}");
    var body        = await apiResponse.Content.ReadAsStringAsync();

    return Results.Content(body, "application/json", statusCode: (int)apiResponse.StatusCode);
});

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.Run();

// ─── Вспомогательные методы ───────────────────────────────────────────────────

bool TryGetValidSession(HttpRequest req, out SessionData? sess, out string? sessionId)
{
    sess = null; sessionId = null;
    if (!req.Cookies.TryGetValue("session", out sessionId) || sessionId is null)
        return false;
    if (!sessions.TryGetValue(sessionId, out sess))
        return false;
    if (DateTime.UtcNow >= sess.SessionExpiry)
    {
        sessions.TryRemove(sessionId, out _);
        return false;
    }
    return true;
}

string RotateSession(string oldId, SessionData sess, HttpResponse response)
{
    sessions.TryRemove(oldId, out _);
    var newId = NewSessionId();
    sessions[newId] = sess;
    response.Cookies.Append("session", newId, new CookieOptions
    {
        HttpOnly = true,
        Secure   = false,
        SameSite = SameSiteMode.Lax,
        MaxAge   = TimeSpan.FromSeconds(sessionTtlSeconds),
    });
    return newId;
}

async Task<bool> RefreshTokenAsync(SessionData sess)
{
    try
    {
        using var http = new HttpClient();
        var form = new Dictionary<string, string>
        {
            ["grant_type"]    = "refresh_token",
            ["refresh_token"] = sess.RefreshToken,
            ["client_id"]     = clientId,
        };
        if (!string.IsNullOrEmpty(clientSecret))
            form["client_secret"] = clientSecret;

        var resp = await http.PostAsync(tokenUrl, new FormUrlEncodedContent(form));
        if (!resp.IsSuccessStatusCode) return false;

        var json = await resp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);
        sess.AccessToken  = doc.RootElement.GetProperty("access_token").GetString()!;
        sess.TokenExpiry  = DateTime.UtcNow.AddSeconds(accessTokenTtlSeconds);
        if (doc.RootElement.TryGetProperty("refresh_token", out var rt))
            sess.RefreshToken = rt.GetString()!;
        return true;
    }
    catch { return false; }
}

// ─── Модель данных сессии ────────────────────────────────────────────────────
class SessionData
{
    public string AccessToken   { get; set; } = "";
    public string RefreshToken  { get; set; } = "";
    public DateTime TokenExpiry   { get; set; }
    public DateTime SessionExpiry { get; set; }
    public string UserId   { get; set; } = "";
    public string Username { get; set; } = "";
}
