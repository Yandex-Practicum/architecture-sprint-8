using System.Text.Json.Serialization;

namespace bionicpro_auth_api.Models;

/// <summary>
/// Модель для хранения токенов в Redis
/// </summary>
public record TokenData
{
    [JsonPropertyName("access_token")]
    public required string AccessToken { get; set; }

    [JsonPropertyName("refresh_token")]
    public required string RefreshToken { get; set; }

    [JsonPropertyName("expires_in")]
    public int ExpiresIn { get; set; }

    [JsonPropertyName("refresh_expires_in")]
    public int RefreshExpiresIn { get; set; }

    [JsonPropertyName("token_type")]
    public string? TokenType { get; set; }

    [JsonPropertyName("scope")]
    public string? Scope { get; set; }

    [JsonPropertyName("created_at")]
    public DateTime CreatedAt { get; set; }

    [JsonPropertyName("session_state")]
    public string? SessionState { get; set; }

    [JsonPropertyName("id_token")]
    public string? IdToken { get; set; }
}
