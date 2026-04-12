using bionicpro_auth.Models;

namespace bionicpro_auth.Components.Handlers
{
    public interface IAuthService
    {

        Task<SessionData> LoginAsyncAsync(string login, string password, string? otp);

        Task<SessionData> RefreshSessionAsync(Guid sessionId);

        Task LogoutAsync(Guid sessionId);
    }
}
