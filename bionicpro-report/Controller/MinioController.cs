using bionicpro_report.Components;
using bionicpro_report.Components.Implementation;
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
public class MinioController : ControllerBase
{
    private readonly IS3Storage _s3Storage;
    private readonly IReportService _reportService;
    private readonly ILogger<ReportsController> _logger;

    public MinioController(IS3Storage s3Storage, IReportService reportService, ILogger<ReportsController> logger)
    {
        _s3Storage = s3Storage;
        _reportService = reportService;
        _logger = logger;
    }

    /// <summary>
    /// Получение отчёта по пользователю
    /// </summary>
    /// <returns>Отчёт с данными о работе протеза</returns>
    [HttpGet("my")]
    public async Task<ActionResult<ReportResponse>> GetUserReport([FromQuery] DateTime? dateFrom = null, [FromQuery] DateTime? dateTo = null)
    {
        try
        {
            List<Claim> claims = GetClaimsFromAuthorization(HttpContext);

            string userId = claims.First(c => c.Type == "sub")!.Value as string;

            if (dateFrom is null)
            {
                dateFrom = new DateTime(2000, 1, 1);
            }
            if (dateTo is null)
            {
                dateTo = DateTime.Now;
            }

            var reportId = _s3Storage.GenerateReportId(userId, dateFrom!.Value, dateTo!.Value);

            if (await _s3Storage.ReportExistsAsync(claims.First(c => c.Type == "sub")?.Value as string, reportId))
            {
                // Отчет найден в S3 — возвращаем CDN ссылку
                var cdnUrl = _s3Storage.GetReportUrl(userId, reportId);

                _logger.LogInformation($"Report found in S3: {cdnUrl}");

                return Ok(new MinioReportResponse
                {
                    ReportId = reportId,
                    CdnUrl = cdnUrl,
                    FromCache = true,
                    GeneratedAt = DateTime.UtcNow,
                    CachedUntil = DateTime.UtcNow.AddDays(7)
                });
            }
            else
            {
                var report = await _reportService.GetUserReportAsync(userId, dateFrom, dateTo);
                var newReportId = await _s3Storage.UploadReportAsync(userId, reportId, report);
                var cdnUrl = _s3Storage.GetReportUrl(userId, reportId);

                return Ok(new MinioReportResponse
                {
                    ReportId = reportId,
                    CdnUrl = cdnUrl,
                    FromCache = false,
                    GeneratedAt = DateTime.UtcNow,
                    CachedUntil = DateTime.UtcNow.AddDays(7)
                });
            }
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
