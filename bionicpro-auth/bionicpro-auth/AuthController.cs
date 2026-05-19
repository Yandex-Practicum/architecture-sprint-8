using bionicpro_auth.models;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authentication.OpenIdConnect;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.OpenApi.Validations.Rules;
using System.Net;
using System.Net.Mime;

namespace bionicpro_auth
{
    /// <summary>
    /// Принцип работы этой сессии:
    /// Вы переходите на http://localhost:XXXX/login.
    /// Бэкенд понимает, что у вас нет сессии, и делает Challenge в Keycloak.
    /// Вы вводите в браузере user1 / password123.
    /// Keycloak возвращает Authorization Code вашему бэкенду.
    /// Бэкенд в фоновом режиме меняет этот код на JWT токен в Keycloak.
    /// Бэкенд шифрует JWT токен, данные пользователя и упаковывает их в Cookie-файл reportsApp_session.
    /// При каждом следующем запросе браузер передает Cookie.Бэкенд «знает», кто вы, и вы можете в любой момент достать JWT токен через HttpContext.GetTokenAsync("access_token") для отправки во внешние микросервисы.
    /// </summary>
    [ApiController]
    [Route("api/[controller]")]
    public class AuthController : ControllerBase
    {
        /// <summary>
        /// Перенаправление пользователя на страницу входа Keycloak
        /// </summary>
        /// <param name="returnUrl">URL, куда вернуть пользователя после успешного входа</param>
        /// <response code="302">Перенаправление на сервер авторизации Keycloak</response>
        [HttpGet("login")]
        [AllowAnonymous]
        public IActionResult Login([FromQuery] string returnUrl = "/")
        {
            // Инструктируем .NET вызвать цепочку авторизации OIDC.
            // Пользователь уйдет на форму Keycloak, введет пароль там, 
            // Keycloak вернет его на бэкенд, бэкенд запишет куку и вернет на returnUrl.
            return Challenge(new AuthenticationProperties { RedirectUri = returnUrl },
                OpenIdConnectDefaults.AuthenticationScheme);
        }

        /// <summary>
        /// Уничтожение локальной сессии и сессии на сервере Keycloak (Logout)
        /// </summary>
        [HttpGet("logout")]
        [Authorize]
        public IActionResult Logout()
        {
            // SignOut очистит куку "reports_session" на бэкенде 
            // и автоматически отправит фоновый/фронтовой запрос в Keycloak для закрытия сессии там
            return SignOut(new AuthenticationProperties { RedirectUri = "/" },
                CookieAuthenticationDefaults.AuthenticationScheme,
                OpenIdConnectDefaults.AuthenticationScheme);
        }

        /// <summary>
        /// Получение JWT-токенов текущей активной сессии
        /// </summary>
        /// <remarks>Метод используется фронтендом для получения токена из защищенной куки</remarks>
        [HttpGet("token")]
        [Authorize]
        [ProducesResponseType(typeof(AuthResponse), StatusCodes.Status200OK)]
        [ProducesResponseType(StatusCodes.Status401Unauthorized)]
        public async Task<IActionResult> GetSessionTokenAsync()
        {
            // Извлекаем токены, которые .NET сохранил в куку благодаря options.SaveTokens = true в Program.cs
            var accessToken = await HttpContext.GetTokenAsync("access_token");
            var refreshToken = await HttpContext.GetTokenAsync("refresh_token");

            if (string.IsNullOrEmpty(accessToken))
            {
                return Unauthorized("Токен отсутствует в текущей сессии.");
            }

            return Ok(new AuthResponse(accessToken, refreshToken ?? string.Empty));
        }
    }
}
