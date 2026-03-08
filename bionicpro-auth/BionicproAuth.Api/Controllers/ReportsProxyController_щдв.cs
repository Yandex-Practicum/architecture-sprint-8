using System.Net.Http.Headers;
using BionicproAuth.Api.Model;
using Microsoft.AspNetCore.Mvc;

namespace BionicproAuth.Api.Controllers;

[ApiController]
[Route("api/proxy/reports2")]
public class ReportsProxyController2 : ControllerBase
{
    private readonly HttpClient _httpClient;
    private readonly IConfiguration _config;

    public ReportsProxyController2(IHttpClientFactory httpClientFactory, IConfiguration config)
    {
        _httpClient = httpClientFactory.CreateClient();
        _config = config;
    }

    [HttpGet]
    public async Task<IActionResult> GetReport()
    {
        var session = HttpContext.Items["Session"] as SessionData;
        if (session == null)
            return Unauthorized();

        var request = new HttpRequestMessage(HttpMethod.Get, $"{_config["ApiProxy:ReportServiceUrl"]}/reports");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", session.AccessToken);

        var response = await _httpClient.SendAsync(request);
        var content = await response.Content.ReadAsStringAsync();

        return Content(content, response.Content.Headers.ContentType?.MediaType ?? "application/json");
    }
}