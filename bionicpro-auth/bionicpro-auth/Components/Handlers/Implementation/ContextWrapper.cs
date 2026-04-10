using bionicpro_auth.Models.Settings;
using Microsoft.Extensions.Options;

namespace bionicpro_auth.Components.Handlers.Implementation
{
    public class ContextWrapper(IOptionsMonitor<SessionSettings> settings) : IContextWrapper
    {
        public void UpdateSessionCookie(HttpContext context, Guid sessionId)
        {
            var cookieOptions = new CookieOptions
            {
                HttpOnly = true,
                Secure = context.Request.IsHttps,
                SameSite = SameSiteMode.Strict,
                Expires = DateTime.UtcNow.Add(settings.CurrentValue.SessionLifeTime)
            };

            context.Response.Cookies.Append(settings.CurrentValue.CookiesName, sessionId.ToString(), cookieOptions);
        }
    }
}
