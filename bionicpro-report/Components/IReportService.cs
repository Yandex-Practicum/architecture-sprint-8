using bionicpro_report.Models;

namespace bionicpro_report.Components
{
    public interface IReportService
    {
        Task<ReportResponse> GetUserReportAsync(string userId, DateTime? dateFrom = null, DateTime? dateTo = null);
    }
}
