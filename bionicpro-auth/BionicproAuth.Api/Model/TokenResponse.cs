namespace BionicproAuth.Api.Model;

public class TokenResponse
{
    public string AccessToken { get; set; }
    public string RefreshToken { get; set; }
    public int ExpiresIn { get; set; }             // Время жизни access token в секундах
    public int RefreshExpiresIn { get; set; }      // Время жизни refresh token
    public string TokenType { get; set; }
    public string IdToken { get; set; }
}