using bionicpro_auth.Components.Handlers;
using bionicpro_auth.Components.Middleware;
using bionicpro_auth.Models;
using bionicpro_auth.Models.Exception;
using bionicpro_auth.Models.Rest;
using bionicpro_auth.Models.Settings;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;

namespace bionicpro_auth.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class AuthController(
                        IAuthService authService,
                        IContextWrapper contextWrapper,
                        IOptionsMonitor<SessionSettings> settings,
                        ILogger<AuthController> logger) : ControllerBase
    {

        [HttpPost("login")]
        public async Task<IActionResult> Login([FromBody] LoginRequest login)
        {
            logger.LogInformation("I am on login");
            try
            {
                SessionData session = await authService.LoginAsyncAsync(login.UserName, login.Pass, login.Otp);

                contextWrapper.UpdateSessionCookie(HttpContext, session.SessionId);

                return Ok(new
                {
                    user = new
                    {
                        userId = session.UserInfo.UserId,
                        username = session.UserInfo.UserName,
                        createdAt = session.AccessTokenCreateAt,
                        expiry = session.AccessTokenExpiry,
                        expireIn = session.AccessTokenCreateAt + session.AccessTokenExpiry
                    },
                    message = "Login successful"
                });
            }
            catch (OtpRequiredException)
            {
                return Unauthorized(new
                {
                    success = false,
                    requiresOtp = true,
                });
            }
            catch (Exception e)
            {
                return Unauthorized("Authentication failed");
            }
        }

        [SessionRotate]
        [HttpGet("me")]
        public async Task<IActionResult> GetCurrentUser()
        {
            // Информация о пользователе доступна через middleware
            if (HttpContext.Items["Session"] is SessionData session)
            {
                return Ok(new
                {
                    userId = session.UserInfo.UserId,
                    username = session.UserInfo.UserName,
                    createdAt = session.AccessTokenCreateAt,
                    expiry = session.AccessTokenExpiry,
                    expireIn = session.AccessTokenCreateAt + session.AccessTokenExpiry
                });
            }

            return Unauthorized(new { error = "Not authenticated" });
        }

        [SessionRotate]
        [HttpGet("validate")]
        public IActionResult ValidateSession()
        {
            if (HttpContext.Items["Session"] != null)
            {
                return Ok(new { valid = true });
            }

            return Unauthorized(new { valid = false });
        }

        [HttpPost("logout")]
        public async Task<IActionResult> Logout()
        {
            var cookieName = settings.CurrentValue.CookiesName;

            if (Request.Cookies.TryGetValue(cookieName, out var rawSessionId) &&
                Guid.TryParse(rawSessionId, out Guid sessionId))
            {

                await authService.LogoutAsync(sessionId);

                Response.Cookies.Delete(cookieName);
            }

            return Ok(new { message = "Logout successful" });
        }

    }
}
