using Microsoft.AspNetCore.Mvc;
using report_service.DTOs;
using report_service.Services;
using Microsoft.Extensions.Logging;
using report_service.Models;

namespace report_service.Controllers;

[ApiController]
[Route("api/reports")]
public class ReportController(IReportService reportService, ILogger<ReportController> logger, IS3Service s3Service) : ControllerBase
{
    private readonly IReportService _reportService = reportService;
    private readonly ILogger<ReportController> _logger = logger;
    private readonly IS3Service _s3Service = s3Service;

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

        var s3Key = $"reports/{userId}/latest.json";
        
        if (await _s3Service.ExistsAsync(s3Key))
        {
            _logger.LogInformation("Report found in S3 for user {UserId}", userId);
            var report = await _s3Service.GetJsonAsync<UserReport>(s3Key);
            return Ok(new ReportResponse
            {
                UserId = userId,
                Report = report,
                GeneratedAt = DateTime.UtcNow
            });
        }

        try
        {
            var report = await _reportService.GetReportByUserAsync(userId);

            if (report == null)
            {
                return NotFound(new { message = $"No report found for user {userId}" });
            }

            await _s3Service.UploadJsonAsync(s3Key, report);

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
            return StatusCode(500, new { error = "Internal server error" });
        }
    }
}