using bionicpro_report.Models;

namespace bionicpro_report.Components
{
    public interface IClickHouseService
    {
        Task<List<ProsthesisReport>> GetUserReportsAsync(string userId);
        Task<bool> UserExistsAsync(string userId);
        Task<List<string>> GetUserProsthesesAsync(string userId);
    }
}
