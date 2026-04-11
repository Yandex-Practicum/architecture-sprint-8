using ClickHouse.Client.ADO;
using ClickHouse.Client.ADO.Parameters;
using Microsoft.AspNetCore.Authorization;
using System.Data;

namespace reports_backend.Services
{
    public interface IClickhouseCLientService
    {
        Task<DateTime> GetLastAvalailableReportDateAsync(string userEmail);
        Task<List<ReportRecordDTO>> GetReportRecordsAsync(string userEmail);
    }

    public class ClickHouseService(ClickHouseDataSource dataSource) : IClickhouseCLientService
    {
        public async Task<DateTime> GetLastAvalailableReportDateAsync(string userEmail)
        {
            await using var connection = dataSource.CreateConnection();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT MAX(event_end_time) FROM prosthesis_events_datamart WHERE user_email = {user_email:String}";
            command.Parameters.Add(new ClickHouseDbParameter { ParameterName = "user_email", Value = userEmail });
            await using var reader = await command.ExecuteReaderAsync();

            await reader.ReadAsync();
            var max_report_date = reader.GetDateTime(0);     // Max(event_end_time)

            return max_report_date;
        }

        public async Task<List<ReportRecordDTO>> GetReportRecordsAsync(string userEmail)
        {
            await using var connection = dataSource.CreateConnection();
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT * FROM prosthesis_events_datamart WHERE user_email = {user_email:String}";
            command.Parameters.Add(new ClickHouseDbParameter { ParameterName = "user_email", Value = userEmail});
            await using var reader = await command.ExecuteReaderAsync();

            var results = new List<ReportRecordDTO>();
            while (await reader.ReadAsync())
            {
                results.Add(new ReportRecordDTO(
                    reader.GetDateTime(0),       // event_start_time
                    reader.GetDateTime(1),       // event_end_time
                    reader.GetString(2),         // movement_type
                    Convert.ToInt32(reader.GetValue(3)),// movements_count
                    Convert.ToInt32(reader.GetValue(4)),// user_id
                    reader.GetString(5),         // user_first_name
                    reader.GetString(6),         // user_last_name
                    reader.GetString(7)          // user_email
                ));
            }

            return results;
        }
    }

    public record ReportRecordDTO(
      DateTime EventStartTime,
      DateTime EventEndTime,
      string MovementType,
      int MovementsCount,
      int UserId,
      string UserFirstName,
      string UserLastName,
      string UserEmail
  );
}
