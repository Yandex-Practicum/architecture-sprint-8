using Microsoft.AspNetCore.Mvc;
using report_service.DTOs;
using report_service.Services;
using Microsoft.Extensions.Logging;

namespace report_service.Controllers;

[ApiController]
[Route("api/reports")]
public class ReportController(IReportService reportService, ILogger<ReportController> logger) : ControllerBase
{
    private readonly IReportService _reportService = reportService;
    private readonly ILogger<ReportController> _logger = logger;

    [HttpGet("{userId}")]
    public async Task<IActionResult> GetUserReport(string userId)
    {
        var currentUserId = User.FindFirst("sub")?.Value;
        if (string.IsNullOrEmpty(currentUserId))
        {
            return Unauthorized(new { error = "User not authenticated" });
        }

        if (currentUserId != userId)
        {
            return Forbid(); 
        }
        
        try
        {
            var report = await _reportService.GetReportByUserAsync(userId);

            if (report == null)
            {
                _logger.LogWarning("No report found for user {UserId}", userId);
                return NotFound(new { message = $"No report found for user {userId}" });
            }

            var response = new ReportResponse
            {
                UserId = userId,
                Report = report,
                GeneratedAt = DateTime.UtcNow
            };

            return Ok(response);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing request for user {UserId}", userId);
            return StatusCode(500, new { error = "Internal server error" });
        }
    }
}