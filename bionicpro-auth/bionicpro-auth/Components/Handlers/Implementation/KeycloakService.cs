using bionicpro_auth.Components.Handlers;
using bionicpro_auth.Models;
using NETCore.Keycloak.Client.HttpClients.Abstraction;
using NETCore.Keycloak.Client.Models;
using NETCore.Keycloak.Client.Models.Auth;
using NETCore.Keycloak.Client.Models.Tokens;
using NETCore.Keycloak.Client.Models.Users;

namespace bionicpro_auth.Components.Handlers.Implementation
{
    public class KeycloakService(
                            IKeycloakClient client,
                            IConfiguration config) : IKeyCloakService
    {
        private KcClientCredentials clientCreds => new()
        {
            ClientId = config["Keycloak:credentials:client-id"],
            Secret = config["Keycloak:credentials:secret"]
        };



        public async Task<KcIdentityProviderToken> LoginAsync(string userName, string password)
        {
            KcResponse<KcIdentityProviderToken> tokenResponse = await client.Auth.GetResourceOwnerPasswordTokenAsync(
                config["Keycloak:realm"],
                clientCreds,
                new KcUserLogin()
                {
                    Username = userName,
                    Password = password
                }
            );


            if (tokenResponse.IsError)
            {
                throw tokenResponse.Exception;
            }

            return tokenResponse.Response;
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

        public async Task<KcIdentityProviderToken> RefreshAccessTokenAsync(string refreshToken)
        {
            KcResponse<KcIdentityProviderToken> tokenResponse = await client.Auth.RefreshAccessTokenAsync(config["Keycloak:realm"], clientCreds, refreshToken);
            if (tokenResponse.IsError)
            {
                throw new InvalidOperationException("Can`t refresh access token");
            }
            return tokenResponse.Response;
        }

        public async Task<bool> RevokeTokenAsync(string refreshToken)
        {
            return (await client.Auth.RevokeRefreshTokenAsync(config["Keycloak:realm"], clientCreds, refreshToken)).Response;
        }
    }
}
