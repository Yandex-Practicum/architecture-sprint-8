using bionicpro_auth.Models;
using bionicpro_auth.Models.Exception;

namespace bionicpro_auth.Components.Handlers.Implementation
{
    public class AuthService(
                    IKeyCloakService keycloakService,
                    ISessionService sessionService,
                    IEncryptor encryptor) : IAuthService
    {



        public async Task<SessionData> LoginAsyncAsync(string login, string password, string? otp)
        {
            AuthResult loginResponse = await keycloakService.LoginAsync(login, password, otp);

            if (!loginResponse.IsSuccess && loginResponse.RequiresOtp)
            {
                throw new OtpRequiredException();
            }
            else if (!loginResponse.IsSuccess)
            {
                throw new UnauthorizedAccessException();
            }

            UserInfo userInfo = await keycloakService.GetUserInfoAsync(loginResponse.Tokens.AccessToken);

            return sessionService.CreateSession(userInfo, loginResponse.Tokens);
        }

        public async Task<SessionData> RefreshSessionAsync(Guid sessionId)
        {
            SessionData session = sessionService.GetSession(sessionId);

            AuthResult loginResponse = await keycloakService.RefreshAccessTokenAsync(encryptor.Decrypt(session.EncryptedRefreshToken));

            sessionService.RemoveSession(sessionId);
            if (!loginResponse.IsSuccess)
            {
                throw new UnauthorizedAccessException();
            }
            return sessionService.CreateSession(session.UserInfo, loginResponse.Tokens);
        }

        public async Task LogoutAsync(Guid sessionId)
        {
            SessionData session = sessionService.GetSession(sessionId);
            sessionService.RemoveSession(sessionId);
        }
    }
}
