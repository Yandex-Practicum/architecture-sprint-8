using bionicpro_auth.Models;

namespace bionicpro_auth.Components.Handlers
{
    public interface ISessionService
    {

        SessionData CreateSession(UserInfo userInfo, KeycloakTokenResponse token);
        SessionData GetSession(Guid SessionId);
        Guid RotateSession(Guid oldSessionId);
        void RemoveSession(Guid oldSessionId);

    }
}
