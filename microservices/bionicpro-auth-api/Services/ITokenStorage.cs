using bionicpro_auth_api.Models;

namespace bionicpro_auth_api.Services;

/// <summary>
/// Интерфейс хранилища
/// </summary>
public interface ITokenStorage
{
    Task StoreTokensAsync(string sessionId, TokenResponse tokens);

    Task<TokenResponse?> GetTokensAsync(string sessionId);

    Task RemoveTokensAsync(string sessionId);

    Task SaveYandexUserAsync(string key, string value);

    Task StoreYandexTokensAsync(string sessionId, string accessToken, string refreshToken);

    Task<YandexTokens?> GetYandexTokensAsync(string sessionId);
}
