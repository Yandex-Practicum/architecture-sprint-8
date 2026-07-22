namespace bionicpro_auth_api.Models;

public class YandexTokenResponse
{
    [System.Text.Json.Serialization.JsonPropertyName("access_token")]
    public string? AccessToken { get; set; }

    [System.Text.Json.Serialization.JsonPropertyName("refresh_token")]
    public string? RefreshToken { get; set; }

    [System.Text.Json.Serialization.JsonPropertyName("expires_in")]
    public int ExpiresIn { get; set; }
}