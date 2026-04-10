using bionicpro_auth.Models;

namespace bionicpro_auth.Components.Handlers
{
    public interface ICacheWrapper
    {

        void SetSession(Guid sessionId, SessionData session, TimeSpan? expiry = null);
        
        bool TryGetSession(Guid sessionId, out SessionData? session);

        void Clear(Guid sessionSessionId);
    }
}
