using bionicpro_reports.models;
using Dapper;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Npgsql;

namespace bionicpro_reports
{
    [ApiController]
    [Route("api/[controller]")]
    [Authorize] // Защищаем весь контроллер проверкой куки
    public class ReportsController : ControllerBase
    {
        private readonly string _connectionString;

        public ReportsController(IConfiguration configuration)
        {
            // Строка подключения к вашей БД PostgreSQL
            _connectionString = configuration.GetConnectionString("Reports")
                ?? "Host=postgres;Database=airflow;Username=airflow;Password=airflow";
        }

        [HttpGet("my")]
        public async Task<IActionResult> GetBuyerSummaryReport()
        {
             var currentUserId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;

            using var connection = new NpgsqlConnection(_connectionString);

            var query = $@"
                SELECT 
                    buyer_id AS BuyerId, 
                    total_orders AS TotalOrders, 
                    total_spent AS TotalSpent, 
                    total_discount AS TotalDiscount, 
                    avg_sensor_value AS AvgSensorValue, 
                    max_power AS MaxPower 
                FROM buyer_summary_report;";

            var reportData = await connection.QueryAsync<BuyerSummaryReport>(query);

            return Ok(reportData.FirstOrDefault());
        }
    }
}
