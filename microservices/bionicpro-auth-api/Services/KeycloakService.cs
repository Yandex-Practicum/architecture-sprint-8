using bionicpro_auth_api.Models;
using System.Text.Json;

namespace bionicpro_auth_api.Services;

public class KeycloakService(HttpClient httpClient, IConfiguration config, ILogger<KeycloakService> logger) : IKeycloakService
{
    private readonly HttpClient _httpClient = httpClient;
    private readonly IConfiguration _config = config;
    private readonly ILogger<KeycloakService> _logger = logger;

    public string GetAuthorizationUrl(string state, string redirectUri)
    {
        var config = _config.GetSection("Keycloak");

        return $"{config["AuthServerUrl"]}realms/{config["Realm"]}/protocol/openid-connect/auth?" +
               $"client_id={config["Resource"]}&" +
               $"redirect_uri={redirectUri}&" +
               $"response_type=code&" +
               $"scope=openid profile email offline_access&" +
               $"state={state}";
    }

    public async Task<TokenResponse?> ExchangeCodeForTokensAsync(string code, string redirectUri)
    {
        var config = _config.GetSection("Keycloak");
        var tokenEndpoint = $"{config["AuthServerUrl"]}realms/{config["Realm"]}/protocol/openid-connect/token";

        var parameters = new List<KeyValuePair<string, string>>
        {
            new("grant_type", "authorization_code"),
            new("code", code),
            new("redirect_uri", redirectUri),
            new("client_id", config["Resource"]!),
            new("client_secret", config["Credentials:Secret"]!)
        };

        var response = await _httpClient.PostAsync(tokenEndpoint, new FormUrlEncodedContent(parameters));
        response.EnsureSuccessStatusCode();

        var content = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<TokenResponse>(content);
    }

    public async Task<TokenResponse?> RefreshTokenAsync(string refreshToken)
    {
        var config = _config.GetSection("Keycloak");
        var tokenEndpoint = $"{config["AuthServerUrl"]}realms/{config["Realm"]}/protocol/openid-connect/token";

        var parameters = new List<KeyValuePair<string, string>>
        {
            new("grant_type", "refresh_token"),
            new("refresh_token", refreshToken),
            new("client_id", config["Resource"]!),
            new("client_secret", config["Credentials:Secret"]!)
        };

        var response = await _httpClient.PostAsync(tokenEndpoint, new FormUrlEncodedContent(parameters));
        response.EnsureSuccessStatusCode();

        var content = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<TokenResponse>(content);
    }

    public async Task<bool> ValidateTokenAsync(string accessToken)
    {
        try
        {
            var config = _config.GetSection("Keycloak");
            var introspectionEndpoint = $"{config["AuthServerUrl"]}realms/{config["Realm"]}/protocol/openid-connect/token/introspect";

            var parameters = new List<KeyValuePair<string, string>>
            {
                new("token", accessToken),
                new("client_id", config["Resource"]!),
                new("client_secret", config["Credentials:Secret"]!)
            };

            var response = await _httpClient.PostAsync(introspectionEndpoint, new FormUrlEncodedContent(parameters));
            response.EnsureSuccessStatusCode();

            var content = await response.Content.ReadAsStringAsync();
            var result = JsonSerializer.Deserialize<IntrospectionResponse>(content);

            return result?.Active == true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error validating token");
            return false;
        }
    }

    public async Task LogoutAsync(string refreshToken)
    {
        var config = _config.GetSection("Keycloak");
        var logoutEndpoint = $"{config["AuthServerUrl"]}realms/{config["Realm"]}/protocol/openid-connect/logout";

        var parameters = new List<KeyValuePair<string, string>>
        {
            new("refresh_token", refreshToken),
            new("client_id", config["Resource"]!),
            new("client_secret", config["Credentials:Secret"]!)
        };

        await _httpClient.PostAsync(logoutEndpoint, new FormUrlEncodedContent(parameters));
    }
}
