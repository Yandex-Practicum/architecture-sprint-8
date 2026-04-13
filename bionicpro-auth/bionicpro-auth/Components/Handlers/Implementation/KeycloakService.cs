using bionicpro_auth.Models;
using bionicpro_auth.Models.Settings;
using Microsoft.Extensions.Options;
using System.Net.Http;
using System.Text.Json;

namespace bionicpro_auth.Components.Handlers.Implementation
{
    public class KeycloakService(
                            HttpClient httpClient,
                            IOptionsMonitor<KeycloakSettings> settings,
                            ILogger<KeycloakService> logger) : IKeyCloakService
    {

        /// <summary>
        /// Генерация URL для авторизации в Keycloak (с PKCE)
        /// </summary>
        public string GenerateAuthorizationUrl( string state, string redirectUri, string? kcIdpHint = null)
        {
            var baseUrl = $"{settings.CurrentValue.BaseUrl.TrimEnd('/')}/realms/{settings.CurrentValue.Realm}/protocol/openid-connect/auth";

            List<string> parameters =
            [
                $"response_type=code",
                $"client_id={settings.CurrentValue.FrontendCredentional.ClientId}",
                $"redirect_uri={Uri.EscapeDataString(redirectUri)}",
                $"scope=openid profile email",
                $"state={state}"
            ];

            if (!string.IsNullOrEmpty(kcIdpHint))
            {
                parameters.Add($"kc_idp_hint={kcIdpHint}");
            }

            return $"{baseUrl}?{string.Join("&", parameters)}";
        }

        /// <summary>
        /// Обмен authorization code на токены
        /// </summary>
        public async Task<AuthResult?> ExchangeCodeForTokensAsync(string code, string redirectUri)
        {
            try
            {
                var tokenUrl = $"{settings.CurrentValue.BaseUrl.TrimEnd('/')}/realms/{settings.CurrentValue.Realm}/protocol/openid-connect/token";

                var content = new FormUrlEncodedContent([
                        new KeyValuePair<string, string>("grant_type", "authorization_code"),
                        new KeyValuePair<string, string>("client_id", settings.CurrentValue.BackendCredentional.ClientId),
                        new KeyValuePair<string, string>("client_secret", settings.CurrentValue.BackendCredentional.Secret),
                        new KeyValuePair<string, string>("code", code),
                        new KeyValuePair<string, string>("redirect_uri", redirectUri)
                ]);

                var response = await httpClient.PostAsync(tokenUrl, content);
                var json = await response.Content.ReadAsStringAsync();

                if (!response.IsSuccessStatusCode)
                {
                    return new AuthResult() { IsSuccess = false, ErrorMessage = $"Token exchange failed: {json}" };
                }

                return new AuthResult() { IsSuccess = true, Tokens = JsonSerializer.Deserialize<KeycloakTokenResponse>(json) };
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Token exchange failed");
                return new AuthResult() { IsSuccess = false, ErrorMessage = $"Token exchange failed: {ex.Message}" };
            }
        }

        public async Task<UserInfo> GetUserInfoAsync(string accessToken)
        {
            try
            {
                var userInfoUrl = $"{settings.CurrentValue.BaseUrl}/realms/{settings.CurrentValue.Realm}/protocol/openid-connect/userinfo";

                httpClient.DefaultRequestHeaders.Clear();
                httpClient.DefaultRequestHeaders.Add("Authorization", $"Bearer {accessToken}");

                var response = await httpClient.GetAsync(userInfoUrl);
                var json = await response.Content.ReadAsStringAsync();

                if (!response.IsSuccessStatusCode)
                {
                    return null;
                }

                return JsonSerializer.Deserialize<UserInfo>(json, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                })!;
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Failed to get user info");
                return null;
            }

        }

        public async Task<AuthResult> RefreshAccessTokenAsync(string refreshToken)
        {
            try
            {

                var tokenEndpoint = $"{settings.CurrentValue.BaseUrl.Trim('/')}/realms/{settings.CurrentValue.Realm}/protocol/openid-connect/token";
                var content = new FormUrlEncodedContent(new[]
                {
                    new KeyValuePair<string, string>("grant_type", "refresh_token"),
                    new KeyValuePair<string, string>("client_id", settings.CurrentValue.BackendCredentional.ClientId),
                    new KeyValuePair<string, string>("client_secret", settings.CurrentValue.BackendCredentional.Secret),
                    new KeyValuePair<string, string>("refresh_token", refreshToken)
                });

                var response = await httpClient.PostAsync(tokenEndpoint, content);
                var json = await response.Content.ReadAsStringAsync();

                if (response.IsSuccessStatusCode)
                {
                    var tokens = JsonSerializer.Deserialize<KeycloakTokenResponse>(json);
                    return new AuthResult()
                    {
                        IsSuccess = true,
                        Tokens = tokens
                    };
                }

                var error = JsonSerializer.Deserialize<KeycloakErrorResponse>(json);
                return new AuthResult()
                {
                    IsSuccess = false,
                    ErrorMessage = error?.ErrorDescription ?? "Token refresh failed"
                };
            }
            catch
            {
                return new AuthResult()
                {
                    IsSuccess = false,
                    ErrorMessage = "Internal server error"
                };
            }
        }

    }
}
