using bionicpro_auth.Models;

namespace bionicpro_auth.Components.Handlers
{
    public interface IKeyCloakService
    {

        Task<AuthResult> LoginAsync(string userName, string password, string? otp);

        Task<UserInfo> GetUserInfoAsync(string accessToken);

        Task<AuthResult> RefreshAccessTokenAsync(string refreshToken);

    }
}
