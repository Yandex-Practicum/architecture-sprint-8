using bionicpro_report.Models;
using Microsoft.Extensions.Caching.Distributed;
using System.Text.Json;

namespace bionicpro_report.Components.Implementation
{
    public class ReportService : IReportService
    {
        private readonly IClickHouseService _clickHouseService;
        //private readonly IDistributedCache _cache;
        private readonly ILogger<ReportService> _logger;
        private readonly int _cacheExpiryMinutes;

        public ReportService(
            IClickHouseService clickHouseService,
            IConfiguration configuration,
            ILogger<ReportService> logger)
        {
            _clickHouseService = clickHouseService;
        }

        public async Task<ReportResponse> GetUserReportAsync(
            string userId)
        {

            if (!await _clickHouseService.UserExistsAsync(userId))
            {
                throw new KeyNotFoundException($"User {userId} not found");
            }

            var reports = await _clickHouseService.GetUserReportsAsync(
                userId);

            // Формирование ответа
            var response = new ReportResponse
            {
                UserId = userId,
                Reports = reports,
                Summary = CalculateSummary(reports),
                GeneratedAt = DateTime.UtcNow
            };

            // Сохранение в кеш
            //var cacheOptions = new DistributedCacheEntryOptions
            //{
            //    AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(_cacheExpiryMinutes)
            //};

            //await _cache.SetStringAsync(cacheKey, JsonSerializer.Serialize(response), cacheOptions);

            //_logger.LogInformation("Generated report for user {UserId} with {Count} records", userId, reports.Count);

            return response;
        }

        public async Task<bool> CanAccessUserDataAsync(UserContext userContext, string targetUserId)
        {
            // Администратор имеет доступ ко всем данным
            if (userContext.Roles.Contains("admin") || userContext.Roles.Contains("support"))
            {
                return true;
            }

            // Пользователь имеет доступ только к своим данным
            if (userContext.UserId == targetUserId)
            {
                return true;
            }

            // Проверка, что пользователь владеет протезом (дополнительная проверка)
            var userProstheses = await _clickHouseService.GetUserProsthesesAsync(targetUserId);
            if (userProstheses.Any(p => userContext.ProsthesisIds.Contains(p)))
            {
                return true;
            }

            return false;
        }

        private ReportSummary CalculateSummary(List<ProsthesisReport> reports)
        {
            if (reports == null || !reports.Any())
            {
                return new ReportSummary
                {
                    Recommendation = "Недостаточно данных для формирования рекомендаций"
                };
            }

            var summary = new ReportSummary
            {
                OverallAvgReactionTime = reports.Average(r => r.AvgReactionTimeMs),
                OverallSuccessRate = 1 - reports.Average(r => r.MisclassificationRate),
                TotalMovements = reports.Sum(r => r.TotalSignals),
                DaysWithData = reports.Select(r => r.ReportDate.Date).Distinct().Count()
            };

            // Формирование рекомендации
            if (summary.OverallAvgReactionTime > 100)
            {
                summary.Recommendation = "Рекомендуется донастройка протеза: время реакции превышает 100 мс";
            }
            else if (summary.OverallSuccessRate < 0.85)
            {
                summary.Recommendation = "Рекомендуется калибровка: низкая точность распознавания движений";
            }
            else if (reports.Any(r => r.MinBatteryLevel < 20))
            {
                summary.Recommendation = "Рекомендуется частая зарядка батареи";
            }
            else
            {
                summary.Recommendation = "Протез работает в штатном режиме";
            }

            return summary;
        }
    }

}
