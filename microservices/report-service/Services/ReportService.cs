using report_service.Models;
using Microsoft.Extensions.Logging;

namespace report_service.Services;

public class ReportService(IClickHouseRepository repository, ILogger<ReportService> logger) : IReportService
{
    private readonly IClickHouseRepository _repository = repository;
    private readonly ILogger<ReportService> _logger = logger;

    public async Task<UserReport?> GetReportByUserAsync(string userId)
    {
        _logger.LogInformation("Getting report for user {UserId}", userId);
        return await _repository.GetLatestReportByUserAsync(userId);
    }
}