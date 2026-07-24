using report_service.Models;

namespace report_service.Services;

public interface IReportService
{
    Task<UserReport?> GetReportByUserAsync(string userId);
}