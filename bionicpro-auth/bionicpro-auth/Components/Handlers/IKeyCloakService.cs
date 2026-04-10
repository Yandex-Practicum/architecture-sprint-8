using bionicpro_auth.Models;
using NETCore.Keycloak.Client.Models.Tokens;

namespace bionicpro_auth.Components.Handlers
{
    public interface IKeyCloakService
    {

        Task<KcIdentityProviderToken> LoginAsync(string userName, string password);

        Task<UserInfo> GetUserInfoAsync(string accessToken);

        Task<KcIdentityProviderToken> RefreshAccessTokenAsync(string refreshToken);

        Task<bool> RevokeTokenAsync(string refreshToken);

    }
}
