using Octonica.ClickHouseClient;
using Dapper;
using Microsoft.Extensions.Logging;
using report_service.Models;

namespace report_service.Services;

public class ClickHouseRepository : IClickHouseRepository, IDisposable
{
    private readonly ILogger<ClickHouseRepository> _logger;
    private ClickHouseConnection? _connection;

    public ClickHouseRepository(ILogger<ClickHouseRepository> logger)
    {
        _logger = logger;
    }

    public async Task<UserReport?> GetLatestReportByUserAsync(string userId)
    {
        var connectionString = "Host=clickhouse;Port=9000;Database=bionicpro;User=report;Password=report;";

        try
        {
            _connection = new ClickHouseConnection(connectionString);
            await _connection.OpenAsync();

            var command = _connection.CreateCommand();
            command.CommandText = @"
                SELECT 
                    user_id AS UserId,
                    user_email AS UserEmail,
                    user_name AS UserName,
                    total_steps AS TotalSteps,
                    total_active_minutes AS TotalActiveMinutes,
                    battery_avg_usage AS AvgBattery,
                    error_count AS ErrorCount,
                    report_date AS ReportDate
                FROM bionicpro.user_report_mart
                WHERE user_id = @userId
                ORDER BY report_date DESC
                LIMIT 1
            ";

            var parameter = command.CreateParameter();
            parameter.ParameterName = "userId";
            parameter.Value = userId;
            command.Parameters.Add(parameter);

            using var reader = await command.ExecuteReaderAsync();

            if (await reader.ReadAsync())
            {
                return new UserReport
                {
                    UserId = reader.GetString(reader.GetOrdinal("UserId")),
                    UserEmail = reader.GetString(reader.GetOrdinal("UserEmail")),
                    UserName = reader.GetString(reader.GetOrdinal("UserName")),
                    TotalSteps = reader.GetInt64(reader.GetOrdinal("TotalSteps")),
                    TotalActiveMinutes = reader.GetInt64(reader.GetOrdinal("TotalActiveMinutes")),
                    AvgBattery = reader.GetDouble(reader.GetOrdinal("AvgBattery")),
                    ErrorCount = reader.GetInt64(reader.GetOrdinal("ErrorCount")),
                    ReportDate = reader.GetDateTime(reader.GetOrdinal("ReportDate"))
                };
            }

            return null;
        }
        catch (Exception ex)
        {
            throw;
        }
    }

    public void Dispose() => _connection?.Dispose();
}