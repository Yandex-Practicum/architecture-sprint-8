using bionicpro_report.Models;

namespace bionicpro_report.Components
{
    public interface IClickHouseService
    {
        Task<List<ProsthesisReport>> GetUserReportsAsync(string userId, DateTime? dateFrom = null, DateTime? dateTo = null);
        Task<bool> UserExistsAsync(string userId);
        Task<List<string>> GetUserProsthesesAsync(string userId);
    }
}
