using bionicpro_auth.Components.Handlers;
using bionicpro_auth.Models;
using Microsoft.Extensions.Caching.Memory;

namespace bionicpro_auth.Components.Handlers.Implementation
{
    public class CacheWrapper(IMemoryCache cache) : ICacheWrapper
    {
        public void SetSession(Guid sessionId, SessionData session, TimeSpan? expiry = null)
        {
            cache.Set($"session-{sessionId}", session, expiry ?? TimeSpan.FromHours(1));
        }

        public bool TryGetSession(Guid sessionId, out SessionData? session)
        {
            return cache.TryGetValue($"session-{sessionId}", out session);
        }

        public void Clear(Guid sessionId)
        {
            cache.Remove($"session-{sessionId}");
        }
    }
}
