using bionicpro_auth.Models;
using bionicpro_auth.Models.Settings;
using Microsoft.Extensions.Options;

namespace bionicpro_auth.Components.Handlers.Implementation
{
    public class SessionService(
                        ICacheWrapper cacheWrapper,
                        IEncryptor encryptor,
                        IOptionsMonitor<SessionSettings> sessionSetings) : ISessionService
    {
        public SessionData CreateSession(UserInfo userInfo, KeycloakTokenResponse token)
        {

            SessionData sessionData = new()
            {
                SessionId = Guid.NewGuid(),
                UserInfo = userInfo,
                AccessToken = token.AccessToken,
                AccessTokenExpiry = TimeSpan.FromSeconds(token.ExpiresIn),
                RefreshTokenExpiry = TimeSpan.FromSeconds(token.RefreshExpiresIn),
                EncryptedRefreshToken = encryptor.Encrypt(token.RefreshToken),
                SessionCreateAt = DateTime.Now,
                AccessTokenCreateAt = DateTime.Now
            };

            cacheWrapper.SetSession(sessionData.SessionId, sessionData, sessionSetings.CurrentValue.SessionLifeTime);

            return sessionData;
        }

        public SessionData GetSession(Guid sessionId)
        {
            if (cacheWrapper.TryGetSession(sessionId, out SessionData? session))
            {
                return session;
            }

            throw new KeyNotFoundException("Session is missed");
        }

        public Guid RotateSession(Guid oldSessionId)
        {
            SessionData session = GetSession(oldSessionId);

            session.SessionId = Guid.NewGuid();

            cacheWrapper.SetSession(session.SessionId, session, sessionSetings.CurrentValue.SessionLifeTime);
            cacheWrapper.Clear(oldSessionId);

            return session.SessionId;
        }

        public void RemoveSession(Guid oldSessionId)
        {
            cacheWrapper.Clear(oldSessionId);
        }

    }
}
