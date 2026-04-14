using bionicpro_auth.Models;

namespace bionicpro_auth.Components.Handlers
{
    public interface IKeyCloakService
    {
        string GenerateAuthorizationUrl(string state,string codeChallange,  string redirectUri, string? kcIdpHint = null);

        Task<AuthResult?> ExchangeCodeForTokensAsync(string code, string codeVerify, string redirectUri);

        Task<UserInfo> GetUserInfoAsync(string accessToken);

        Task<AuthResult> RefreshAccessTokenAsync(string refreshToken);
        Task LogoutFromKeycloak(string refreshToken);

    }
}
