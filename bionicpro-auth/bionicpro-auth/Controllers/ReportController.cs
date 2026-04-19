using bionicpro_auth.Components.Handlers;
using bionicpro_auth.Components.Handlers.Implementation;
using bionicpro_auth.Components.Middleware;
using bionicpro_auth.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Caching.Memory;
using static System.Runtime.InteropServices.JavaScript.JSType;

namespace bionicpro_auth.Controllers
{
    [ApiController]
    [Route("api/reports")]
    public class ReportsController : ControllerBase
    {
        private readonly IReportsProxyService _reportProxyService;
        private readonly IConfiguration _config;
        private readonly IMemoryCache _cache;
        private readonly ISessionService _sessionService;

        public ReportsController(
            IReportsProxyService reportProxyService,
            IConfiguration config,
            ISessionService sessionService,
            IMemoryCache cache)
        {
            _reportProxyService = reportProxyService;
            _sessionService = sessionService;
            _config = config;
            _cache = cache;
        }

        // Проксирование запроса с добавлением JWT токена
        [SessionRotate]
        [HttpGet("my")]
        public async Task<IActionResult> GetMyReportsAsync()
        {
            var sessionId = HttpContext.Items["Session"] as Guid?;

            if (sessionId is null)
            {
                return Unauthorized();
            }

            SessionData session = _sessionService.GetSession(sessionId!.Value);

            HttpResponseMessage response = await _reportProxyService.ProxyGetAsync($"{_config["ReportsApi:Url"]}/api/reports/my", session!.AccessToken);

            response.EnsureSuccessStatusCode();

            string content = await response.Content.ReadAsStringAsync();

            return Content(content, "application/json");
        }

        // Проксирование запроса с добавлением JWT токена
        [SessionRotate]
        [HttpGet("minio")]
        public async Task<IActionResult> GetMyReportsAsync(DateTime? dateFrom, DateTime? dateTo)
        {
            var sessionId = HttpContext.Items["Session"] as Guid?;

            if (sessionId is null)
            {
                return Unauthorized();
            }

            SessionData session = _sessionService.GetSession(sessionId!.Value);

            if (dateFrom is null)
            {
                dateFrom = new DateTime(2000, 1, 1);
            }
            if (dateTo is null)
            {
                dateTo = DateTime.Now;
            }

            HttpResponseMessage response = await _reportProxyService.ProxyGetAsync($"{_config["ReportsApi:Url"]}/api/minio/my?dateFrom={dateFrom}&dateTo={dateTo}", session!.AccessToken);

            response.EnsureSuccessStatusCode();

            string content = await response.Content.ReadAsStringAsync();

            return Content(content, "application/json");
        }
    }
}
