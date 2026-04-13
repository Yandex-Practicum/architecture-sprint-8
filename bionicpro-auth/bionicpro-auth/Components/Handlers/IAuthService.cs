using bionicpro_auth.Models;

namespace bionicpro_auth.Components.Handlers
{
    public interface IAuthService
    {


        Task<SessionData> RefreshSessionAsync(Guid sessionId);

    }
}
