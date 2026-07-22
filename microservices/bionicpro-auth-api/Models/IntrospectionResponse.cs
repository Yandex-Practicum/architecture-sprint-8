using System.Text.Json.Serialization;

namespace bionicpro_auth_api.Models;

public record IntrospectionResponse
{
    [JsonPropertyName("active")]
    public bool Active { get; set; }

    [JsonPropertyName("sub")]
    public string? Subject { get; set; }
}