using report_service.Models;

namespace report_service.Services;

public interface IClickHouseRepository
{
    Task<UserReport?> GetLatestReportByUserAsync(string userId);
}