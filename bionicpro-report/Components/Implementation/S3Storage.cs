using bionicpro_report.Models;
using Minio;
using Minio.DataModel;
using Minio.DataModel.Args;
using System.Text.Json;

namespace bionicpro_report.Components.Implementation
{
    public class S3Storage : IS3Storage
    {
        private readonly IMinioClient _minioClient;
        private readonly IConfiguration _config;
        private readonly ILogger<S3Storage> _logger;

        public S3Storage(
                        IConfiguration config,
                        IMinioClient minioClient,
                           ILogger<S3Storage> logger)
        {
            _minioClient = minioClient;
            _config = config;
            _logger = logger;
        }

        private string GetBucketName() => _config["Minio:BucketName"] ?? "bionicpro-reports";
        private string GetCdnBaseUrl() => _config["Cdn:BaseUrl"] ?? "http://cdn.bio-pro.local:8081/reports/";

        public string GenerateReportId(string userId, DateTime from, DateTime till)
        {
            return $"{userId}/{from:yyyy-MM-dd}/report_{till:yyyyMMdd_HHmmss}.json";
        }

        private string GetObjectName(string userId, string reportId)
        {
            return $"users/{userId}/reports/{reportId}.json";
        }

        public async Task<bool> ReportExistsAsync(string userId, string reportId)
        {
            try
            {
                var objectName = GetObjectName(userId, reportId);
                var args = new StatObjectArgs()
                    .WithBucket(GetBucketName())
                    .WithObject(objectName);

                ObjectStat stat = await _minioClient.StatObjectAsync(args);

                _logger.LogDebug($"Stat {JsonSerializer.Serialize(stat)}");

                return true;
            }
            catch (Exception ex)
            {
                _logger.LogDebug($"Report {reportId} not found in S3: {ex.Message}");
                return false;
            }
        }

        public async Task<string> UploadReportAsync(string userId, string reportId, ReportResponse report)
        {
            try
            {
                var objectName = GetObjectName(userId, reportId);
                var json = JsonSerializer.Serialize(report, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase });

                var jsonBytes = System.Text.Encoding.UTF8.GetBytes(json);

                using var stream = new MemoryStream(jsonBytes);

                var putArgs = new PutObjectArgs()
                    .WithBucket(GetBucketName())
                    .WithObject(objectName)
                    .WithStreamData(stream)
                    .WithObjectSize(stream.Length)
                    .WithContentType("application/json");

                await _minioClient.PutObjectAsync(putArgs);

                _logger.LogInformation($"Report uploaded to S3: {objectName}");

                return reportId;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to upload report to S3");
                throw;
            }
        }

        public string GetReportUrl(string userId, string reportId)
        {
            var cdnBaseUrl = GetCdnBaseUrl();
            var objectName = GetObjectName(userId, reportId);

            return new Uri(new Uri(cdnBaseUrl), objectName).ToString();
        }
    }
}
