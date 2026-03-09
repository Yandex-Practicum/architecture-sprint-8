using BionicproReport;
using BionicproReport.Dtos;
using BionicproReport.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Dapper;
using QuestPDF.Fluent;

namespace ReportService.Controllers;

[Authorize]
[ApiController]
[Route("api/[controller]")]
public class ReportsController : ControllerBase
{
    private readonly DapperContext _context;
    private readonly IReportStorage _reportStorage;
    private readonly ILogger<ReportsController> _logger;
    
    public ReportsController(DapperContext context, IReportStorage reportStorage, ILogger<ReportsController> logger)
    {
        _context = context;
        _reportStorage = reportStorage;
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
        
        // Проверяем наличие готового отчёта
        var reportUrl = await _reportStorage.GetReportUrlAsync(userId);
        if (reportUrl != null)
            return Ok(new { reportUrl });

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
        
        // Генерация PDF (используем QuestPDF)
        var pdfBytes = GeneratePdf(report);
        using var stream = new MemoryStream(pdfBytes);

        // Сохраняем в S3
        await _reportStorage.GenerateAndStoreReportAsync(userId, stream);

        // Получаем свежую ссылку
        var newUrl = await _reportStorage.GetReportUrlAsync(userId);
        return Ok(new { reportUrl = newUrl });
        
    }
    
    private byte[] GeneratePdf(ReportDto report)
    {
        using var stream = new MemoryStream();
        var document = Document.Create(container =>
        {
            container.Page(page =>
            {
                page.Margin(50);
                page.Header().Text($"Report for {report.FullName}").SemiBold().FontSize(20);
                page.Content().Column(col =>
                {
                    col.Item().Text($"Email: {report.Email}");
                    col.Item().Text($"Total sessions: {report.TotalSessions}");
                    col.Item().Text($"Total active minutes: {report.TotalActiveMinutes}");
                    col.Item().Text($"Total steps: {report.TotalSteps}");
                    col.Item().Text($"Average battery usage: {report.AvgBatteryUsage}%");
                    col.Item().Text($"Last session: {report.LastSessionDate:d}");
                });
            });
        });
        document.GeneratePdf(stream);
        return stream.ToArray();
    }
}