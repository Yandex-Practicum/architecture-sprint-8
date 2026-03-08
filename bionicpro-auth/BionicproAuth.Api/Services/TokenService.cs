using System.Text.Json;
using BionicproAuth.Api.Model;

namespace BionicproAuth.Api.Services;

public class TokenService : ITokenService
{
    private readonly HttpClient _httpClient;
    private readonly IConfiguration _config;

    public TokenService(HttpClient httpClient, IConfiguration config)
    {
        _httpClient = httpClient;
        _config = config;
    }

    public async Task<TokenResponse> ExchangeCodeForTokensAsync(string code, string codeVerifier)
    {
        var tokenEndpoint = $"{_config["Keycloak:Authority"]}/protocol/openid-connect/token";
        var parameters = new Dictionary<string, string>
        {
            ["grant_type"] = "authorization_code",
            ["client_id"] = _config["Keycloak:ClientId"],
            ["redirect_uri"] = _config["Keycloak:RedirectUri"],
            ["code"] = code,
            ["code_verifier"] = codeVerifier
        };

        var response = await _httpClient.PostAsync(tokenEndpoint, new FormUrlEncodedContent(parameters));
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<TokenResponse>(json, new JsonSerializerOptions(){PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower});
    }

    public async Task<TokenResponse> RefreshAccessTokenAsync(string refreshToken)
    {
        var tokenEndpoint = $"{_config["Keycloak:Authority"]}/protocol/openid-connect/token";
        var parameters = new Dictionary<string, string>
        {
            ["grant_type"] = "refresh_token",
            ["client_id"] = _config["Keycloak:ClientId"],
            ["refresh_token"] = refreshToken
        };

        var response = await _httpClient.PostAsync(tokenEndpoint, new FormUrlEncodedContent(parameters));
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<TokenResponse>(json);
    }
}