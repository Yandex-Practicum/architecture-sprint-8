using bionicpro_auth_api.Models;

namespace bionicpro_auth_api.Services;

/// <summary>
/// Интерфейс для работы с Keycloak
/// </summary>
public interface IKeycloakService
{
    string GetAuthorizationUrl(string state, string redirectUri);

    Task<TokenResponse?> ExchangeCodeForTokensAsync(string code, string redirectUri);

    Task<TokenResponse?> RefreshTokenAsync(string refreshToken);

    Task<bool> ValidateTokenAsync(string accessToken);

    Task LogoutAsync(string refreshToken);
}
