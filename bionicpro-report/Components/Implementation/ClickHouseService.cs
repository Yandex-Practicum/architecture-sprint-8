using bionicpro_report.Models;
using ClickHouse.Client.ADO;
using System.Data;
using System.Text;

namespace bionicpro_report.Components.Implementation
{
    public class ClickHouseService : IClickHouseService
    {
        private readonly string _connectionString;
        private readonly ILogger<ClickHouseService> _logger;

        public ClickHouseService(IConfiguration configuration, ILogger<ClickHouseService> logger)
        {
            _connectionString = configuration.GetConnectionString("ClickHouse") ??
                throw new ArgumentNullException("ClickHouse connection string not configured");
            _logger = logger;
        }

        public async Task<List<ProsthesisReport>> GetUserReportsAsync(string userId, DateTime? dateFrom = null, DateTime? dateTo = null)
        {
            var reports = new List<ProsthesisReport>();

            var query = @"
            SELECT 
                prosthesis_id,
                prosthesis_type,
                report_date,
                avg_reaction_time_ms,
                max_reaction_time_ms,
                min_reaction_time_ms,
                total_signals,
                successful_movements,
                failed_movements,
                misclassification_rate,
                avg_battery_level,
                min_battery_level,
                quality_ok,
                tuning_count,
                last_tuning_date
            FROM bionicpro.user_report_mart
            WHERE user_id = '{0}'
            {1}
            ORDER BY report_date DESC";

            StringBuilder dateFileter = new();
            if (dateFrom is not null)
            {
                dateFileter.Append($"AND report_date >= '{dateFrom!.Value.ToString("yyyy-MM-dd")}'");
            }
            if (dateTo is not null)
            {
                dateFileter.Append($"AND report_date <= '{dateTo!.Value.ToString("yyyy-MM-dd")}'");
            }
            var formattedQuery = string.Format(query, userId, dateFileter);


            try
            {
                using var connection = new ClickHouseConnection(_connectionString);
                await connection.OpenAsync();

                using var command = connection.CreateCommand();
                command.CommandText = formattedQuery;
                command.CommandType = CommandType.Text;

                using var reader = await command.ExecuteReaderAsync();

                while (await reader.ReadAsync())
                {
                    reports.Add(new ProsthesisReport
                    {
                        ProsthesisId = reader.GetString(0),
                        ProsthesisType = reader.GetString(1),
                        ReportDate = reader.GetDateTime(2),
                        AvgReactionTimeMs = reader.GetFloat(3),
                        MaxReactionTimeMs = (uint)reader.GetValue(4),
                        MinReactionTimeMs = (uint)reader.GetValue(5),
                        TotalSignals = (uint)reader.GetValue(6),
                        SuccessfulMovements = (uint)reader.GetValue(7),
                        FailedMovements = (uint)reader.GetValue(8),
                        MisclassificationRate = reader.GetFloat(9),
                        AvgBatteryLevel = reader.GetFloat(10),
                        MinBatteryLevel = reader.GetByte(11),
                        QualityOk = reader.GetBoolean(12),
                        TuningCount = (uint)reader.GetValue(13),
                        LastTuningDate = reader.IsDBNull(14) ? null : reader.GetDateTime(14)
                    });
                }

                _logger.LogInformation("Retrieved {Count} reports for user {UserId}", reports.Count, userId);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving reports for user {UserId}", userId);
                throw;
            }

            return reports;
        }

        public async Task<bool> UserExistsAsync(string userId)
        {
            var query = "SELECT COUNT(*) FROM bionicpro.user_report_mart WHERE user_id = '{0}' LIMIT 1";
            var formattedQuery = string.Format(query, userId);

            try
            {
                using var connection = new ClickHouseConnection(_connectionString);
                await connection.OpenAsync();

                using var command = connection.CreateCommand();
                command.CommandText = formattedQuery;

                var count = Convert.ToInt32(await command.ExecuteScalarAsync());
                return count > 0;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error checking user existence for {UserId}", userId);
                return false;
            }
        }

        public async Task<List<string>> GetUserProsthesesAsync(string userId)
        {
            var prostheses = new List<string>();
            var query = "SELECT DISTINCT prosthesis_id FROM bionicpro.user_report_mart WHERE user_id = {0:UserId}";
            var formattedQuery = string.Format(query, userId);

            try
            {
                using var connection = new ClickHouseConnection(_connectionString);
                await connection.OpenAsync();

                using var command = connection.CreateCommand();
                command.CommandText = formattedQuery;

                using var reader = await command.ExecuteReaderAsync();
                while (await reader.ReadAsync())
                {
                    prostheses.Add(reader.GetString(0));
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving prostheses for user {UserId}", userId);
            }

            return prostheses;
        }
    }
}
