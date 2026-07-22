using System.Text.Json.Serialization;

namespace bionicpro_auth_api.Models;

public record TokenResponse
{
    [JsonPropertyName("access_token")]
    public required string AccessToken { get; set; }

    [JsonPropertyName("refresh_token")]
    public string? RefreshToken { get; set; }

    [JsonPropertyName("expires_in")]
    public int? ExpiresIn { get; set; }

    [JsonPropertyName("refresh_expires_in")]
    public int? RefreshExpiresIn { get; set; }

    [JsonPropertyName("token_type")]
    public string? TokenType { get; set; }

    [JsonPropertyName("scope")]
    public string? Scope { get; set; }
}
