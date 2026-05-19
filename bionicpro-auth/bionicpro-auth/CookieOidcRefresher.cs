using System.Globalization;
using bionicpro_auth.models;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.IdentityModel.Protocols.OpenIdConnect;

namespace bionicpro_auth
{
    public class CookieOidcRefresher : CookieAuthenticationEvents
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly IConfiguration _configuration;

        public CookieOidcRefresher(IHttpClientFactory httpClientFactory, IConfiguration configuration)
        {
            _httpClientFactory = httpClientFactory;
            _configuration = configuration;
        }

        public override async Task ValidatePrincipal(CookieValidatePrincipalContext context)
        {
            var tokens = context.Properties.GetTokens();

            // 1. Ищем время окончания действия текущего access_token
            var expiresAtToken = tokens.FirstOrDefault(t => t.Name == "expires_at");
            if (expiresAtToken == null || !DateTimeOffset.TryParse(expiresAtToken.Value, CultureInfo.InvariantCulture, out var expiresAt))
            {
                return;
            }

            // 2. Если токен будет жить еще дольше 10 секунд — ничего не делаем
            if (expiresAt > DateTimeOffset.UtcNow.AddSeconds(10))
            {
                return;
            }

            // 3. Токен истекает. Ищем refresh_token для его обновления
            var refreshToken = tokens.FirstOrDefault(t => t.Name == OpenIdConnectParameterNames.RefreshToken)?.Value;
            if (string.IsNullOrEmpty(refreshToken))
            {
                context.RejectPrincipal(); // Сбрасываем сессию, если обновиться невозможно
                return;
            }

            try
            {
                // 4. Запрашиваем новые токены у Keycloak через внутреннюю сеть Docker
                var client = _httpClientFactory.CreateClient();
                var tokenResponse = await client.PostAsync(
                    _configuration["Keycloak:TokenAddress"],
                    new FormUrlEncodedContent(new Dictionary<string, string>
                    {
                        { "grant_type", "refresh_token" },
                        { "refresh_token", refreshToken },
                        { "client_id", "reports-frontend" }
                    })
                );

                if (!tokenResponse.IsSuccessStatusCode)
                {
                    context.RejectPrincipal(); // Keycloak отклонил refresh_token (сессия полностью протухла)
                    return;
                }

                var payload = await tokenResponse.Content.ReadFromJsonAsync<KeycloakTokenResponse>();
                if (payload == null) return;

                // 5. Считаем новое время жизни access_token
                var newExpiresAt = DateTimeOffset.UtcNow.AddSeconds(payload.ExpiresIn);

                // 6. Обновляем значения токенов в оперативной памяти текущего запроса
                context.Properties.UpdateTokenValue("access_token", payload.AccessToken);
                context.Properties.UpdateTokenValue("refresh_token", payload.RefreshToken ?? refreshToken);
                context.Properties.UpdateTokenValue("expires_at", newExpiresAt.ToString("o", CultureInfo.InvariantCulture));

                // 7. Говорим ASP.NET Core перевыпустить (обновить) Set-Cookie в ответе браузеру
                context.ShouldRenew = true;
            }
            catch
            {
                context.RejectPrincipal(); // В случае сетевого сбоя инвалидируем сессию ради безопасности
            }
        }
    }
}
