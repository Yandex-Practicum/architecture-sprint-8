using System.Security.Claims;
using BionicproReport.Dtos;
using BionicproReport.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using QuestPDF.Fluent;

namespace ReportService.Controllers;

//[Authorize]
[AllowAnonymous]
[ApiController]

[Route("api/[controller]")]
public class ReportsController : ControllerBase
{
    private readonly IReportStorage _reportStorage;
    private readonly IClickHouseReportService _reportService;
    private readonly ILogger<ReportsController> _logger;

    public ReportsController(
        IReportStorage reportStorage,
        IClickHouseReportService reportService,
        ILogger<ReportsController> logger)
    {
        _reportStorage = reportStorage;
        _reportService = reportService;
        _logger = logger;
    }

    [HttpGet]
    public async Task<ActionResult<ReportDto>> GetReport()
    {  uint userId = 19;
        // Получаем идентификатор пользователя из токена (JWT)
        /*var userIdClaim = User.FindFirst("sub") ?? User.FindFirst(ClaimTypes.NameIdentifier);
        if (userIdClaim == null)
        {
            _logger.LogWarning("User ID not found in token");
            return Unauthorized("Missing user identifier");
        }

        // Парсим userId (в зависимости от того, как он хранится - как число или строка)
        if (!uint.TryParse(userIdClaim.Value, out var userId))
        {
            _logger.LogWarning("Invalid user ID format: {UserIdValue}", userIdClaim.Value);
            return BadRequest("Invalid user ID format");
        }*/

        try
        {
          
            var report = await _reportService.GetReportByUserIdAsync(userId);

            if (report == null)
            {
                return NotFound($"No report found for user {userId}");
            }

            // Генерация PDF (используем QuestPDF)
            var pdfBytes = GeneratePdf(report);
            using var stream = new MemoryStream(pdfBytes);

            // Сохраняем в S3
            await _reportStorage.GenerateAndStoreReportAsync(userId, stream);

            // Получаем свежую ссылку
            var newUrl = await _reportStorage.GetReportUrlAsync(userId);
            return Ok(new {reportUrl = newUrl});
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing report request for user {UserId}", userId);
            return StatusCode(500, "An error occurred while processing your request");
        }
    }

    [HttpGet("health")]
    public IActionResult Health()
    {
        return Ok(new {status = "healthy", timestamp = DateTime.UtcNow});
    }

    private byte[] GeneratePdf(ReportDto report)
    {
        using var stream = new MemoryStream();
        var document = Document.Create(container =>
        {
            container.Page(page =>
            {
                page.Margin(50);
                page.Header().Text($"Report for {report.Name}").SemiBold().FontSize(20);
                page.Content().Column(col =>
                {
                    col.Item().Text($"Age: {report.Age}");
                    col.Item().Text($"Gender: {report.Gender}");
                    col.Item().Text($"Email: {report.Email}");
                    col.Item().Text($"Prosthesis type: {report.ProsthesisType}");

                    col.Item().Text($"Total sessions: {report.TotalSessions}");
                    col.Item().Text($"Total signal duration: {report.TotalSignalDuration}");
                    col.Item().Text($"Average signal frequency: {report.AvgSignalFrequency}");
                    col.Item().Text($"Average signal amplitude: {report.AvgSignalAmplitude}%");
                    col.Item().Text($"Last signal time: {report.LastSignalTime:d}");
                });
            });
        });
        document.GeneratePdf(stream);
        return stream.ToArray();
    }
}