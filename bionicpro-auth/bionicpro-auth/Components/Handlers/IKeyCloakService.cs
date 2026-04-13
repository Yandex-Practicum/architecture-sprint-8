using bionicpro_auth.Models;

namespace bionicpro_auth.Components.Handlers
{
    public interface IKeyCloakService
    {
        string GenerateAuthorizationUrl(string state, string redirectUri, string? kcIdpHint = null);

        Task<AuthResult?> ExchangeCodeForTokensAsync(string code, string redirectUri);

        Task<UserInfo> GetUserInfoAsync(string accessToken);

        Task<AuthResult> RefreshAccessTokenAsync(string refreshToken);

    }
}
