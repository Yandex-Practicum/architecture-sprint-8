using BionicproAuth.Api.Model;

namespace BionicproAuth.Api.Services;

public interface ITokenService
{
    Task<TokenResponse> ExchangeCodeForTokensAsync(string code, string codeVerifier);
    Task<TokenResponse> RefreshAccessTokenAsync(string refreshToken);
}