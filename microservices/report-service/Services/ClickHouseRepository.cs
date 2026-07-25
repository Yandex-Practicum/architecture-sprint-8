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

            command.CommandText = @"
                SELECT 
                    c.user_id AS UserId,
                    c.user_email AS UserEmail,
                    c.user_name AS UserName,
                    c.phone AS UserPhone,
                    c.region AS Region,
                    c.prosthesis_model AS ProsthesisModel,
                    c.purchase_date AS PurchaseDate,
                    s.total_steps AS TotalSteps,
                    s.total_active_minutes AS TotalActiveMinutes,
                    s.avg_battery AS AvgBattery,
                    s.error_count AS ErrorCount,
                    now() AS ReportDate
                FROM crm_clients c
                LEFT JOIN (
                    SELECT 
                        user_id,
                        sum(steps) AS total_steps,
                        sum(active_minutes) AS total_active_minutes,
                        avg(battery_level) AS avg_battery,
                        count(error_code) AS error_count
                    FROM sensor_data
                    WHERE timestamp >= now() - interval 7 day
                    GROUP BY user_id
                ) s ON c.user_id = s.user_id
                WHERE c.user_id = @userId
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