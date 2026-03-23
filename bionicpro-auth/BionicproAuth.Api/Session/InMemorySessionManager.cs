using System.Security.Claims;
using BionicproAuth.Api.Model;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.Extensions.Caching.Memory;

namespace BionicproAuth.Api.Session;

public class InMemorySessionManager : ISessionManager
{
    private readonly IMemoryCache _cache;
    private readonly IDataProtector _protector;
    private readonly IConfiguration _config;

    public InMemorySessionManager(IMemoryCache cache, IDataProtectionProvider dataProtectionProvider, IConfiguration config)
    {
        _cache = cache;
        _protector = dataProtectionProvider.CreateProtector("RefreshTokenProtector");
        _config = config;
    }

    public string CreateSession(TokenResponse tokens, string userId, IEnumerable<Claim> claims)
    {
        var sessionId = Guid.NewGuid().ToString();
        var session = new SessionData
        {
            SessionId = sessionId,
            UserId = userId,
            AccessToken = tokens.AccessToken,
            RefreshToken = _protector.Protect(tokens.RefreshToken), // шифруем refresh token
            AccessTokenExpiresAt = DateTime.UtcNow.AddSeconds(tokens.ExpiresIn),
            RefreshTokenExpiresAt = DateTime.UtcNow.AddSeconds(tokens.RefreshExpiresIn),
            Claims = claims.ToDictionary(c => c.Type, c => (object)c.Value)
        };

        var cacheEntryOptions = new MemoryCacheEntryOptions()
            .SetAbsoluteExpiration(TimeSpan.FromMinutes(_config.GetValue<int>("Session:SessionLifetimeMinutes")));

        _cache.Set(sessionId, session, cacheEntryOptions);
        return sessionId;
    }

    public SessionData GetSession(string sessionId)
    {
        _cache.TryGetValue(sessionId, out SessionData session);
        if (session != null)
        {
            // Расшифровываем refresh token при необходимости (если будем использовать)
            // session.RefreshToken = _protector.Unprotect(session.RefreshToken); 
        }
        return session;
    }

    public void UpdateSession(string sessionId, TokenResponse newTokens)
    {
        if (_cache.TryGetValue(sessionId, out SessionData session))
        {
            session.AccessToken = newTokens.AccessToken;
            session.RefreshToken = _protector.Protect(newTokens.RefreshToken);
            session.AccessTokenExpiresAt = DateTime.UtcNow.AddSeconds(newTokens.ExpiresIn);
            session.RefreshTokenExpiresAt = DateTime.UtcNow.AddSeconds(newTokens.RefreshExpiresIn);

            _cache.Set(sessionId, session, new MemoryCacheEntryOptions()
                .SetAbsoluteExpiration(TimeSpan.FromMinutes(_config.GetValue<int>("Session:SessionLifetimeMinutes"))));
        }
    }
    
    
    public SessionData RotateSession(string oldSessionId, out string newSessionId)
    {
        if (_cache.TryGetValue(oldSessionId, out SessionData session))
        {
            newSessionId = Guid.NewGuid().ToString();
            var newSession = new SessionData
            {
                SessionId = newSessionId,
                UserId = session.UserId,
                AccessToken = session.AccessToken,
                RefreshToken = session.RefreshToken, // уже зашифрован
                AccessTokenExpiresAt = session.AccessTokenExpiresAt,
                RefreshTokenExpiresAt = session.RefreshTokenExpiresAt,
                Claims = session.Claims
            };
            _cache.Remove(oldSessionId);
            _cache.Set(newSessionId, session, new MemoryCacheEntryOptions()
                .SetAbsoluteExpiration(TimeSpan.FromMinutes(_config.GetValue<int>("Session:SessionLifetimeMinutes"))));
            return newSession;
        }
        newSessionId = null;
        return null;
    }

    public void RemoveSession(string sessionId)
    {
        _cache.Remove(sessionId);
    }
}