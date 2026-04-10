using bionicpro_auth.Models;
using NETCore.Keycloak.Client.Models.Tokens;

namespace bionicpro_auth.Components.Handlers.Implementation
{
    public class AuthService(
                    IKeyCloakService keycloakService,
                    ISessionService sessionService,
                    IEncryptor encryptor) : IAuthService
    {
        public async Task<SessionData> LoginAsyncAsync(string login, string password)
        {
            KcIdentityProviderToken token = await keycloakService.LoginAsync(login, password);

            UserInfo userInfo = await keycloakService.GetUserInfoAsync(token.AccessToken);

            return sessionService.CreateSession(userInfo, token);
        }

        public async Task<SessionData> RefreshSessionAsync(Guid sessionId)
        {
            SessionData session = sessionService.GetSession(sessionId);

            KcIdentityProviderToken token = await keycloakService.RefreshAccessTokenAsync(encryptor.Decrypt(session.EncryptedRefreshToken));
            sessionService.RemoveSession(sessionId);

            return sessionService.CreateSession(session.UserInfo, token);
        }

        public async Task LogoutAsync(Guid sessionId)
        {
            SessionData session = sessionService.GetSession(sessionId);
            await keycloakService.RevokeTokenAsync(encryptor.Decrypt(session.EncryptedRefreshToken));
            sessionService.RemoveSession(sessionId);
        }
    }
}
