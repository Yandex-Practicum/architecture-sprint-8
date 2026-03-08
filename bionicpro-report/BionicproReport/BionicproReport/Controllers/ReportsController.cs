using BionicproReport;
using BionicproReport.Dtos;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Dapper;

namespace ReportService.Controllers;

[Authorize]
[ApiController]
[Route("api/[controller]")]
public class ReportsController : ControllerBase
{
    private readonly DapperContext _context;
    private readonly ILogger<ReportsController> _logger;

    public ReportsController(DapperContext context, ILogger<ReportsController> logger)
    {
        _context = context;
        _logger = logger;
    }

    [HttpGet]
    public async Task<ActionResult<ReportDto>> GetReport()
    {
        // Извлекаем идентификатор пользователя из токена (claim "sub")
        var userIdClaim = User.FindFirst("sub") ?? User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier);
        if (userIdClaim == null || !Guid.TryParse(userIdClaim.Value, out var userId))
        {
            _logger.LogWarning("User ID not found in token");
            return Unauthorized("Invalid token: missing user identifier");
        }

        using var connection = _context.CreateConnection();
        const string sql = @"
            SELECT 
                client_id AS ClientId,
                full_name AS FullName,
                email AS Email,
                total_sessions AS TotalSessions,
                total_active_minutes AS TotalActiveMinutes,
                total_steps AS TotalSteps,
                avg_battery_usage AS AvgBatteryUsage,
                last_session_date AS LastSessionDate
            FROM mart_report
            WHERE client_id = @UserId";

        var report = await connection.QuerySingleOrDefaultAsync<ReportDto>(sql, new { UserId = userId });

        if (report == null)
        {
            return NotFound($"No report found for user {userId}");
        }

        return Ok(report);
    }
}