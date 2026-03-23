using BionicproReport.Dtos;
using ClickHouse.Driver;
using ClickHouse.Driver.ADO;
using ClickHouse.Driver.ADO.Parameters;
using ClickHouse.Driver.Utility;


namespace BionicproReport.Services;

public class ClickHouseReportService : IClickHouseReportService
{
    private readonly string _connectionString;
    private readonly string _tableName;
    private readonly ILogger<ClickHouseReportService> _logger;

    public ClickHouseReportService(
        IConfiguration configuration,
        ILogger<ClickHouseReportService> logger)
    {
        _connectionString = configuration.GetConnectionString("ClickHouse")
                            ?? throw new InvalidOperationException("ClickHouse connection string is missing");
        _tableName = configuration["ClickHouse:TableName"] ?? "customer_report_final";
        _logger = logger;
    }

    public async Task<ReportDto?> GetReportByUserIdAsync(uint userId)
    {
        try
        {
            
            var settings = new ClickHouseClientSettings(_connectionString);
            using var client = new ClickHouseClient(settings);

            // Формируем запрос с учетом движка ReplacingMergeTree
            var query = $@"
                SELECT 
                    user_id,
                    name,
                    email,
                    age,
                    gender,
                    country,
                    prosthesis_type,
                    total_sessions,
                    total_signal_duration,
                    avg_signal_frequency,
                    avg_signal_amplitude,
                    last_signal_time,
                    updated_at
                FROM {_tableName}
                FINAL  -- Важно для ReplacingMergeTree, чтобы получить актуальную версию записи
                WHERE user_id = {{userId:Int}}
                ORDER BY updated_at DESC
                LIMIT 1";

            var parameters = new ClickHouseParameterCollection();
            parameters.AddParameter("userId", userId);
            
            using var reader = await client.ExecuteReaderAsync(query, parameters);
          
            if (await reader.ReadAsync())
            {
                return new ReportDto
                {
                    UserId = (uint) reader["user_id"],
                    Name = reader["name"]?.ToString() ?? string.Empty,
                    Email = reader["email"]?.ToString() ?? string.Empty,
                    Age = Convert.ToByte(reader["age"]),
                    Gender = reader["gender"]?.ToString() ?? string.Empty,
                    Country = reader["country"]?.ToString() ?? string.Empty,
                    ProsthesisType = reader["prosthesis_type"]?.ToString() ?? string.Empty,
                    TotalSessions = (uint) (ulong) reader["total_sessions"], // ClickHouse может вернуть ulong
                    TotalSignalDuration = (ulong) reader["total_signal_duration"],
                    AvgSignalFrequency = Convert.ToDouble(reader["avg_signal_frequency"]),
                    AvgSignalAmplitude = Convert.ToDecimal(reader["avg_signal_amplitude"]),
                    LastSignalTime = (DateTime) reader["last_signal_time"],
                    UpdatedAt = (DateTime) reader["updated_at"]
                };
            }

            _logger.LogWarning("No report found for user {UserId}", userId);
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching report for user {UserId}", userId);
            throw; // Пробрасываем исключение для обработки в контроллере
        }
    }
}