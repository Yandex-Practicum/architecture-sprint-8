using Microsoft.Extensions.Caching.Distributed;
using System.Text.Json;
using bionicpro_auth_api.Models;

namespace bionicpro_auth_api.Services;

public class RedisTokenStorage : ITokenStorage
{
    private readonly IDistributedCache _cache;
    private readonly ILogger<RedisTokenStorage> _logger;

    public RedisTokenStorage(IDistributedCache cache, ILogger<RedisTokenStorage> logger)
    {
        _cache = cache;
        _logger = logger;
    }

    public async Task StoreTokensAsync(string sessionId, TokenResponse tokens)
    {
        var key = $"session:{sessionId}:tokens";
        var data = JsonSerializer.Serialize(new
        {
            tokens.AccessToken,
            tokens.RefreshToken,
            tokens.ExpiresIn,
            tokens.RefreshExpiresIn,
            CreatedAt = DateTime.UtcNow
        });

        var options = new DistributedCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = TimeSpan.FromSeconds((double)(tokens.RefreshExpiresIn ?? 300))
        };

        await _cache.SetStringAsync(key, data, options);
    }

    public async Task<TokenResponse?> GetTokensAsync(string sessionId)
    {
        var key = $"session:{sessionId}:tokens";
        var data = await _cache.GetStringAsync(key);

        if (string.IsNullOrEmpty(data))
            return null;

        var tokenData = JsonSerializer.Deserialize<TokenData>(data);
        if (tokenData is null)
            return null;

        return new TokenResponse
        {
            AccessToken = tokenData.AccessToken,
            RefreshToken = tokenData.RefreshToken,
            ExpiresIn = tokenData.ExpiresIn,
            RefreshExpiresIn = tokenData.RefreshExpiresIn
        };
    }

    public async Task RemoveTokensAsync(string sessionId)
    {
        var key = $"session:{sessionId}:tokens";
        await _cache.RemoveAsync(key);
    }

    public async Task SaveYandexUserAsync(string key, string value)
    {
        var options = new DistributedCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = TimeSpan.FromDays(30)
        };
        await _cache.SetStringAsync(key, value, options);
    }

    public async Task StoreYandexTokensAsync(string sessionId, string accessToken, string refreshToken)
    {
        var key = $"session:{sessionId}:yandex_tokens";
        var data = JsonSerializer.Serialize(new
        {
            AccessToken = accessToken,
            RefreshToken = refreshToken,
            CreatedAt = DateTime.UtcNow
        });
        
        var options = new DistributedCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = TimeSpan.FromDays(30)
        };
        
        await _cache.SetStringAsync(key, data, options);
    }

    public async Task<YandexTokens?> GetYandexTokensAsync(string sessionId)
    {
        var key = $"session:{sessionId}:yandex_tokens";
        var data = await _cache.GetStringAsync(key);
        if (string.IsNullOrEmpty(data)) return null;

        return JsonSerializer.Deserialize<YandexTokens>(data);
    }
}