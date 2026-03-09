using System.Text.Json;
using BionicproAuth.Api.Session;

public class TokenExchangeService : ITokenExchangeService
{
    private readonly HttpClient _httpClient;
    private readonly IConfiguration _config;
    private readonly ILogger<TokenExchangeService> _logger;

    public TokenExchangeService(HttpClient httpClient, IConfiguration config, ILogger<TokenExchangeService> logger)
    {
        _httpClient = httpClient;
        _config = config;
        _logger = logger;
    }

    public async Task<string> ExchangeUserTokenAsync(string userAccessToken)
    {
        var tokenEndpoint = $"{_config["Keycloak:BackchannelAuthority"]}/protocol/openid-connect/token";
        
        var parameters = new Dictionary<string, string>
        {
            ["grant_type"] = "urn:ietf:params:oauth:grant-type:token-exchange",
            ["client_id"] = _config["Keycloak:TokenExchangeClient:ClientId"],
            ["client_secret"] = _config["Keycloak:TokenExchangeClient:ClientSecret"],
            ["subject_token"] = userAccessToken,
            ["subject_token_type"] = "urn:ietf:params:oauth:token-type:access_token",
            ["audience"] = _config["Keycloak:ReportsApi:ClientId"]
        };
       
        var requestContent = new FormUrlEncodedContent(parameters);
        var response = await _httpClient.PostAsync(tokenEndpoint, requestContent);
        
        if (!response.IsSuccessStatusCode)
        {
            var error = await response.Content.ReadAsStringAsync();
            _logger.LogError("Token exchange failed. Status: {StatusCode}, Error: {Error}", 
                response.StatusCode, error);
            _logger.LogError("AccessToken: {userAccessToken}", userAccessToken);
            throw new Exception("Token exchange failed");
        }

        var json = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);
        return doc.RootElement.GetProperty("access_token").GetString();
    }
}