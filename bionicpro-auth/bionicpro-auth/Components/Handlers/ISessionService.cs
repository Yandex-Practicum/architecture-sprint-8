using bionicpro_auth.Models;
using NETCore.Keycloak.Client.Models.Tokens;

namespace bionicpro_auth.Components.Handlers
{
    public interface ISessionService
    {

        SessionData CreateSession(UserInfo userInfo, KcIdentityProviderToken token);
        SessionData GetSession(Guid SessionId);
        Guid RotateSession(Guid oldSessionId);
        void RemoveSession(Guid oldSessionId);

    }
}
