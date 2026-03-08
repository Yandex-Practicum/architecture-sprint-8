using System.Net.Http.Headers;
using BionicproAuth.Api.Model;
using BionicproAuth.Api.Session;
using Microsoft.AspNetCore.Mvc;

[ApiController]
[Route("api/proxy")]
public class ReportsProxyController : ControllerBase
{
    private readonly ITokenExchangeService _tokenExchangeService;
    private readonly IConfiguration _config;
    private readonly HttpClient _httpClient;
    private readonly ILogger<ReportsProxyController> _logger;

    public ReportsProxyController(
        ITokenExchangeService tokenExchangeService,
        IConfiguration config,
        IHttpClientFactory httpClientFactory,
        ILogger<ReportsProxyController> logger)
    {
        _tokenExchangeService = tokenExchangeService;
        _config = config;
        _httpClient = httpClientFactory.CreateClient();
        _logger = logger;
    }

    [HttpGet("reports")]
    public async Task<IActionResult> GetReport()
    {
        // Получаем сессию из middleware
        var session = HttpContext.Items["Session"] as SessionData;
        if (session == null)
        {
            _logger.LogWarning("No session found for request");
            return Unauthorized();
        }

        // 1. Обмениваем пользовательский токен на токен для reports-api
        string exchangedToken;
        try
        {
            exchangedToken = await _tokenExchangeService.ExchangeUserTokenAsync(session.AccessToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Token exchange failed for user {UserId}", session.UserId);
            return StatusCode(502, "Authentication service error");
        }

        // 2. Формируем запрос к Report Service
        var reportServiceUrl = _config["ApiProxy:ReportServiceUrl"];
        var request = new HttpRequestMessage(HttpMethod.Get, $"{reportServiceUrl}/api/reports");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", exchangedToken);

        // 3. Отправляем запрос и возвращаем ответ клиенту
        try
        {
            var response = await _httpClient.SendAsync(request);
            var content = await response.Content.ReadAsStringAsync();
            return Content(content, response.Content.Headers.ContentType?.MediaType ?? "application/json");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error proxying request to Report Service");
            return StatusCode(502, "Report service unavailable");
        }
    }
}