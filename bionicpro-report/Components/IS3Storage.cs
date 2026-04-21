using bionicpro_report.Models;

namespace bionicpro_report.Components
{
    public interface IS3Storage
    {
        Task<bool> ReportExistsAsync(string userId, string reportId);
        Task<string> UploadReportAsync(string userId, string reportId, ReportResponse report);
        string GetReportUrl(string userId, string reportId);
        string GenerateReportId(string userId, DateTime from, DateTime to);
    }
}
