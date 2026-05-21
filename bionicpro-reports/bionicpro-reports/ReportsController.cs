using Amazon.S3;
using Amazon.S3.Model;
using Amazon.S3.Util;
using bionicpro_reports.models;
using Dapper;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Npgsql;
using System.Collections.Concurrent;
using System.Text.Json;

namespace bionicpro_reports
{
    [ApiController]
    [Route("api/[controller]")]
    [Authorize]
    public class ReportsController : ControllerBase
    {
        private readonly string _connectionString;

        private readonly IAmazonS3 _s3Client;
        private const string BucketName = "reports";
        // Семафоры для защиты от Cache Stampede (нагрузки при одновременном запросе отчета)
        private static readonly ConcurrentDictionary<string, SemaphoreSlim> _locks = new();


        public ReportsController(IConfiguration configuration, IAmazonS3 s3Client)
        {
            // Строка подключения к вашей БД PostgreSQL
            _connectionString = configuration.GetConnectionString("Reports");
            if (string.IsNullOrWhiteSpace(_connectionString)) throw new NullReferenceException("Section with connection strING IS EMPTY");


            _s3Client = s3Client;
        }

        [HttpGet("my")]
        public async Task<IActionResult> GetMySummaryReport()
        {
            var currentUserId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;

            if (string.IsNullOrEmpty(currentUserId)) return Unauthorized();

            // Структурированный путь внутри бакета MinIO
            var datePath = $"year={DateTime.UtcNow:yyyy}/month={DateTime.UtcNow:MM}/day={DateTime.UtcNow:dd}";
            var s3Key = $"{datePath}/buyer_{currentUserId}.json";


            // ШАГ 1. Проверяем наличие отчета в S3 хранилище через HEAD-запрос
            try
            {
                await _s3Client.GetObjectMetadataAsync(BucketName, s3Key);

                // Файл есть в S3 — генерируем временную подписанную ссылку напрямую на MinIO
                var presignedUrl = GeneratePresignedUrl(s3Key);
                return Ok(new { url = presignedUrl, source = "S3_Storage" });
            }
            catch (AmazonS3Exception ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
            { /* Файла нет в S3 — переходим к блокировке и генерации*/ }

            // Защита от параллельных тяжелых запросов к СУБД от одного пользователя
            var userLock = _locks.GetOrAdd(currentUserId, _ => new SemaphoreSlim(1, 1));
            await userLock.WaitAsync();

            try
            {
                // Double-Check Locking: проверяем, не создал ли файл параллельный поток, пока мы ждали
                try
                {
                    await _s3Client.GetObjectMetadataAsync(BucketName, s3Key);
                    var presignedUrl = GeneratePresignedUrl(s3Key);
                    return Ok(new { url = presignedUrl, source = "S3_Storage_DoubleCheck" });
                }
                catch (AmazonS3Exception) { }


                // ШАГ 2. Чтение данных из OLAP-базы данных
                //using var connection = new NpgsqlConnection(_connectionString);

                // Используем ClickHouseConnection вместо NpgsqlConnection
                using var connection = new ClickHouseConnection(_clickHouseConnectionString);


                var query = $@"
                    SELECT 
                        buyer_id AS BuyerId, 
                        total_orders AS TotalOrders, 
                        total_spent AS TotalSpent, 
                        total_discount AS TotalDiscount, 
                        avg_sensor_value AS AvgSensorValue, 
                        max_power AS MaxPower 
                    FROM buyer_summary_report;";

                var reportData = await connection.QueryFirstOrDefaultAsync<BuyerSummaryReport>(query);

                // ШАГ 3. Сериализация в JSON
                var jsonString = JsonSerializer.Serialize(reportData, new JsonSerializerOptions
                {
                    PropertyNamingPolicy = JsonNamingPolicy.CamelCase
                });

                // Гарантируем наличие бакета в MinIO
                if (!await AmazonS3Util.DoesS3BucketExistV2Async(_s3Client, BucketName))
                {
                    await _s3Client.PutBucketAsync(BucketName);
                }

                // ШАГ 4. Загрузка файла в закрытый бакет S3
                var putRequest = new PutObjectRequest
                {
                    BucketName = BucketName,
                    Key = s3Key,
                    ContentBody = jsonString,
                    ContentType = "application/json"
                };
                await _s3Client.PutObjectAsync(putRequest);

                // Создаем подписанную ссылку для только что загруженного файла
                var freshPresignedUrl = GeneratePresignedUrl(s3Key);
                return Ok(new { url = freshPresignedUrl, source = "Database_Generated" });
            }
            finally
            {
                userLock.Release();
            }
        }


        /// <summary>
        /// Генерирует временную безопасную ссылку на объект в MinIO
        /// </summary>
        private string GeneratePresignedUrl(string s3Key)
        {
            var request = new GetPreSignedUrlRequest
            {
                BucketName = BucketName,
                Key = s3Key,
                Expires = DateTime.UtcNow.AddMinutes(15), // Ссылка сгорит через 15 минут
                Verb = HttpVerb.GET
            };

            return _s3Client.GetPreSignedURL(request);
        }
    }
}
