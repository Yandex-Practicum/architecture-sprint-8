using System.Security.Claims;
using BionicproAuth.Api.Model;

namespace BionicproAuth.Api.Session;

public interface ISessionManager
{
    string CreateSession(TokenResponse tokens, string userId, IEnumerable<Claim> claims);
    SessionData GetSession(string sessionId);
    void UpdateSession(string sessionId, TokenResponse newTokens);
    SessionData RotateSession(string oldSessionId, out string newSessionId);
    void RemoveSession(string sessionId);
}