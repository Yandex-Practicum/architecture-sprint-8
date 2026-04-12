using bionicpro_auth.Models;
using System.Text.Json;

namespace bionicpro_auth.Components.Handlers.Implementation
{
    public class KeycloakService(
                            HttpClient httpClient,
                            IConfiguration config) : IKeyCloakService
    {

        private string _clientId => config["Keycloak:credentials:client-id"];
        private string _secret => config["Keycloak:credentials:secret"];
        private string _tokenEndpoint => config["Keycloak:TokenEndpoint"];

        public async Task<AuthResult> LoginAsync(string userName, string password, string? otp)
        {

            try
            {
                var content = new List<KeyValuePair<string, string>>
                {
                    new("grant_type", "password"),
                    new("client_id", _clientId),
                    new("client_secret", _secret),
                    new("username", userName),
                    new("password", password)
                };

                if (!string.IsNullOrEmpty(otp))
                {
                    content.Add(new KeyValuePair<string, string>("totp", otp));
                }

                var requestContent = new FormUrlEncodedContent(content);
                var response = await httpClient.PostAsync(_tokenEndpoint, requestContent);
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

                var errorResponse = JsonSerializer.Deserialize<KeycloakErrorResponse>(json);

                if (errorResponse?.Error == "invalid_grant")
                {
                    var errorDesc = errorResponse.ErrorDescription?.ToLower() ?? "";

                    if (errorDesc.Contains("otp") || errorDesc.Contains("totp") || errorDesc.Contains("code"))
                    {
                        return new AuthResult
                        {
                            IsSuccess = false,
                            RequiresOtp = true
                        };
                    }
                }

                return new AuthResult
                {
                    IsSuccess = false,
                    ErrorMessage = errorResponse.ErrorDescription
                };
            }
            catch (Exception ex)
            {
                return new AuthResult
                {
                    IsSuccess = false,
                    ErrorMessage = "Unhandled exception"
                };
            }
        }

        public Task<UserInfo> GetUserInfoAsync(string accessToken)
        {
            // Парсим JWT токен для получения sub (user id)
            var handler = new System.IdentityModel.Tokens.Jwt.JwtSecurityTokenHandler();
            var jwtToken = handler.ReadJwtToken(accessToken);

            if (jwtToken.Subject is null)
            {
                throw new InvalidOperationException("User id null or empty");
            }

            return Task.FromResult(new UserInfo()
            {
                UserId = jwtToken.Subject,
                Name = jwtToken.Claims.FirstOrDefault(c => c.Type == "name")?.Value,
                UserName = jwtToken.Claims.FirstOrDefault(c => c.Type == "preferred_username")?.Value ?? "Undefined",
            });

        }

        public async Task<AuthResult> RefreshAccessTokenAsync(string refreshToken)
        {
            try
            {
                var content = new FormUrlEncodedContent(new[]
                {
                    new KeyValuePair<string, string>("grant_type", "refresh_token"),
                    new KeyValuePair<string, string>("client_id", _clientId),
                    new KeyValuePair<string, string>("client_secret", _secret),
                    new KeyValuePair<string, string>("refresh_token", refreshToken)
                });

                var response = await httpClient.PostAsync(_tokenEndpoint, content);
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
