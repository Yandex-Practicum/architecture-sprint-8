using bionicpro_report.Components;
using bionicpro_report.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Authorization.Infrastructure;
using Microsoft.AspNetCore.Mvc;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;

namespace bionicpro_report.Controller;

[ApiController]
[Route("api/[controller]")]
[Produces("application/json")]
public class ReportsController : ControllerBase
{
    private readonly IReportService _reportService;
    private readonly ILogger<ReportsController> _logger;

    public ReportsController(IReportService reportService, ILogger<ReportsController> logger)
    {
        _reportService = reportService;
        _logger = logger;
    }

    /// <summary>
    /// Получение отчёта по пользователю
    /// </summary>
    /// <returns>Отчёт с данными о работе протеза</returns>
    [HttpGet("my")]
    public async Task<ActionResult<ReportResponse>> GetUserReport()
    {
        try
        {
            List<Claim> claims = GetClaimsFromAuthorization(HttpContext);
            var report = await _reportService.GetUserReportAsync(claims.First(c => c.Type == "sub")?.Value as string);
            return Ok(report);
        }
        catch (UnauthorizedAccessException ex)
        {
            _logger.LogWarning(ex, "Unauthorized access attempt");
            return Forbid();
        }
        catch (KeyNotFoundException ex)
        {
            _logger.LogWarning(ex, "User not found");
            return NotFound(new { error = ex.Message });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing report request");
            return StatusCode(500, new { error = "Internal server error" });
        }
    }



    private static List<Claim> GetClaimsFromAuthorization(HttpContext context)
    {

        var token = context.Request.Headers["Authorization"].FirstOrDefault()?.Split(" ").Last();
        SecurityToken validatedToken = new JwtSecurityToken();

        // Извлекаем информацию из токена (пытаемся распарсить)
        var claims = new List<Claim>();

        try
        {
            var handler = new JwtSecurityTokenHandler();
            if (handler.CanReadToken(token))
            {
                var jwtToken = handler.ReadJwtToken(token);
                claims.AddRange(jwtToken.Claims);
            }
        }
        catch
        {
            // Если не удалось распарсить, добавляем заглушку
            claims.Add(new Claim("sub", "unknown-user"));
        }

        return claims;
    }

}
