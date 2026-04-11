using CsvHelper;
using CsvHelper.Configuration;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using reports_backend.Services;
using System.Globalization;
using System.Security.Claims;
using System.Text;

namespace reports_backend.Controllers
{
    [ApiController]
    [Route("reports")]
    public class ReportsController : ControllerBase
    {
        private readonly ILogger<ReportsController> _logger;
        private readonly IClickhouseCLientService _clickClient;
        private string _userEmail => User.FindFirst(ClaimTypes.Email)?.Value
            ?? throw new UnauthorizedAccessException("User email not found in token");
        private string _userName => User.Identity?.Name ?? throw new Exception("User is not defined");


        public ReportsController(ILogger<ReportsController> logger, IClickhouseCLientService clickClient)
        {
            _logger = logger;
            _clickClient = clickClient;
        }

        [HttpGet]
        [Authorize]
        [Route("get_available_date")]
        public async Task<ActionResult<string>> GetLastAvailbaleUserReportDate()
        {
            var data = await _clickClient.GetLastAvalailableReportDateAsync(_userEmail);
            return Ok(data.ToString());
        }



        [HttpGet]
        [Authorize]
        public async Task<FileStreamResult> GetUserReport()
        {
            var data = await _clickClient.GetReportRecordsAsync(_userEmail);
            var config = new CsvConfiguration(CultureInfo.GetCultureInfo("ru-RU"))
            {
                Delimiter = ";"
            };

            var memoryStream = new MemoryStream();
            using (var streamWriter = new StreamWriter(memoryStream, Encoding.GetEncoding(1251), leaveOpen: true))
            using (var csvWriter = new CsvWriter(streamWriter, config))
            {
               await csvWriter.WriteRecordsAsync(data);
                csvWriter.Flush();
            }
            memoryStream.Position = 0;
            return File(memoryStream, "text/csv", $"report_{_userEmail}.csv");
        }
    }
}
