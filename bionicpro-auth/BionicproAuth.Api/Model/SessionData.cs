namespace BionicproAuth.Api.Model;

public class SessionData
{
    public string SessionId { get; set; }          // Уникальный идентификатор сессии
    public string UserId { get; set; }             // Идентификатор пользователя из Keycloak (sub)
    public string AccessToken { get; set; }        // Текущий access token
    public string RefreshToken { get; set; }       // Refresh token (зашифрованный)
    public DateTime AccessTokenExpiresAt { get; set; }
    public DateTime RefreshTokenExpiresAt { get; set; }
    public Dictionary<string, object> Claims { get; set; } // Полезные данные из токена
}