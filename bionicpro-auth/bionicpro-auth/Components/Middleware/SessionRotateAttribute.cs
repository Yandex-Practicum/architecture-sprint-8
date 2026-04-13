using bionicpro_auth.Components.Handlers;
using bionicpro_auth.Models;
using bionicpro_auth.Models.Settings;
using Microsoft.AspNetCore.Mvc.Filters;
using Microsoft.Extensions.Options;
using System.Security.Claims;

namespace bionicpro_auth.Components.Middleware
{
    public class SessionRotateAttribute : ActionFilterAttribute
    {
        public override async Task OnActionExecutionAsync(ActionExecutingContext context, ActionExecutionDelegate next)
        {
            ISessionService sessionService = context.HttpContext.RequestServices.GetService<ISessionService>();
            IAuthService authService = context.HttpContext.RequestServices.GetService<IAuthService>();
            IContextWrapper contextWrapper = context.HttpContext.RequestServices.GetService<IContextWrapper>();
            IOptionsMonitor<SessionSettings> settings = context.HttpContext.RequestServices.GetService<IOptionsMonitor<SessionSettings>>();

            try
            {

                if (context.HttpContext.Request.Cookies.TryGetValue(settings.CurrentValue.CookiesName, out string rawSessionId)
                    && Guid.TryParse(rawSessionId, out Guid sessionId))
                {

                    SessionData session = sessionService.GetSession(sessionId);

                    if (session.AccessTokenCreateAt + session.AccessTokenExpiry > DateTime.Now)
                    {
                        sessionId = sessionService.RotateSession(sessionId);
                        session = sessionService.GetSession(sessionId);
                    }
                    else
                    {
                        session = await authService.RefreshSessionAsync(sessionId);
                    }

                    contextWrapper.UpdateSessionCookie(context.HttpContext, session.SessionId);

                    context.HttpContext.Items["Session"] = session.SessionId;
                }
                else
                {
                    context.HttpContext.Response.Cookies.Delete(settings.CurrentValue.CookiesName);
                }

                await next();
            }
            catch
            {
                context.HttpContext.Response.Cookies.Delete(settings.CurrentValue.CookiesName);
                context.HttpContext.Response.StatusCode = StatusCodes.Status401Unauthorized;
                await context.HttpContext.Response.WriteAsJsonAsync(new { error = "Session expired" });
            }
        }

    }
}
