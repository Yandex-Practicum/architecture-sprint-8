// Report API — сервис отчётов BionicPRO
//
// RBAC: пользователь получает только свой отчёт.
//   → user_id берётся из JWT (sub claim), а не из параметра запроса.
//   → Если параметр user_id передан и не совпадает с sub — 403 Forbidden.
//
// Кеширование: S3 (Minio) → Nginx CDN.
//   1. Проверяем наличие отчёта в S3.
//   2. Если есть — возвращаем CDN URL.
//   3. Если нет  — читаем из ClickHouse, кладём в S3, возвращаем CDN URL.

using System.Text;
using System.Text.Json;
using Amazon.S3;
using Amazon.S3.Model;
using ClickHouse.Client.ADO;

var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

// ─── Конфигурация ────────────────────────────────────────────────────────────
var chHost     = builder.Configuration["ClickHouse:Host"]      ?? "clickhouse";
var chPort     = builder.Configuration["ClickHouse:Port"]      ?? "8123";
var s3Endpoint = builder.Configuration["S3:Endpoint"]          ?? "http://minio:9000";
var s3Key      = builder.Configuration["S3:AccessKey"]         ?? "minioadmin";
var s3Secret   = builder.Configuration["S3:SecretKey"]         ?? "minioadmin";
var s3Bucket   = builder.Configuration["S3:Bucket"]            ?? "reports";
var cdnUrl     = builder.Configuration["Cdn:Url"]              ?? "http://localhost/cdn";

// ─── Вспомогательные функции ─────────────────────────────────────────────────

// Достаём user_id (sub) из Bearer токена в заголовке Authorization
static string? GetUserIdFromToken(HttpRequest request)
{
    var auth = request.Headers.Authorization.ToString();
    if (!auth.StartsWith("Bearer ")) return null;
    var jwt  = auth[7..];
    var parts = jwt.Split('.');
    if (parts.Length < 2) return null;
    var padding = (4 - parts[1].Length % 4) % 4;
    var base64  = parts[1].Replace('-', '+').Replace('_', '/') + new string('=', padding);
    var json    = Encoding.UTF8.GetString(Convert.FromBase64String(base64));
    using var doc = JsonDocument.Parse(json);
    return doc.RootElement.TryGetProperty("sub", out var sub) ? sub.GetString() : null;
}

AmazonS3Client MakeS3Client() => new(s3Key, s3Secret, new AmazonS3Config
{
    ServiceURL            = s3Endpoint,
    ForcePathStyle        = true,
    UseHttp               = true,
    AuthenticationRegion  = "us-east-1",
});

// ─── Эндпоинты ───────────────────────────────────────────────────────────────

// GET /reports?user_id=<optional>
// RBAC: если user_id передан и ≠ sub из токена → 403
app.MapGet("/reports", async (HttpRequest request, string? user_id) =>
{
    // 1. Извлекаем токен и идентифицируем пользователя
    var tokenUserId = GetUserIdFromToken(request);
    if (tokenUserId is null)
        return Results.Unauthorized();

    // 2. RBAC: пользователь может запросить только свой отчёт
    if (user_id is not null && user_id != tokenUserId)
        return Results.Forbid();   // 403

    var reportUserId = tokenUserId;
    var s3Key        = $"reports/{reportUserId}/latest.json";

    // 3. Проверяем S3 кеш (Задание 3)
    var s3 = MakeS3Client();
    try
    {
        var meta = await s3.GetObjectMetadataAsync(s3Bucket, s3Key);
        // Отчёт уже есть в S3 — отдаём CDN URL
        return Results.Ok(new { cdn_url = $"{cdnUrl}/{s3Key}", cached = true });
    }
    catch (AmazonS3Exception ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
    {
        // Не нашли — генерируем
    }

    // 4. Читаем витрину из ClickHouse
    var connStr = $"Host={chHost};Port={chPort};Database=bionicpro;Username=default;Password=clickhouse";
    await using var conn = new ClickHouseConnection(connStr);
    await conn.OpenAsync();

    var cmd = conn.CreateCommand();
    // Запрашиваем только уже обработанные Airflow данные (report_date < today)
    // Если данных нет — честно говорим об этом
    cmd.CommandText = @"
        SELECT
            user_id, username, email,
            prosthesis_id, model,
            total_movements,
            round(avg_response_ms, 2) AS avg_response_ms,
            round(min_response_ms, 2) AS min_response_ms,
            round(max_response_ms, 2) AS max_response_ms,
            toString(last_activity)   AS last_activity,
            toString(report_date)     AS report_date
        FROM bionicpro.user_reports_summary
        WHERE user_id = {userId:String}
          AND report_date < today()
        ORDER BY report_date DESC
        LIMIT 30";
    cmd.Parameters.Add(new ClickHouse.Client.ADO.Parameters.ClickHouseDbParameter
        { ParameterName = "userId", Value = reportUserId });

    var rows = new List<Dictionary<string, object?>>();
    await using var reader = await cmd.ExecuteReaderAsync();
    while (await reader.ReadAsync())
    {
        var row = new Dictionary<string, object?>();
        for (int i = 0; i < reader.FieldCount; i++)
            row[reader.GetName(i)] = reader.GetValue(i);
        rows.Add(row);
    }

    if (rows.Count == 0)
        return Results.NotFound(new { error = "Данных пока нет. Дождитесь следующего запуска Airflow DAG." });

    // 5. Сохраняем в S3 для CDN кеширования
    var report     = new { user_id = reportUserId, generated_at = DateTime.UtcNow, records = rows };
    var reportJson = JsonSerializer.Serialize(report);

    try
    {
        await EnsureBucketExistsAsync(s3, s3Bucket);
        await s3.PutObjectAsync(new PutObjectRequest
        {
            BucketName  = s3Bucket,
            Key         = s3Key,
            ContentBody = reportJson,
            ContentType = "application/json",
        });
    }
    catch (Exception ex)
    {
        Console.WriteLine($"S3 write failed (non-critical): {ex.Message}");
    }

    return Results.Ok(new { cdn_url = $"{cdnUrl}/{s3Key}", cached = false, report });
});

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.Run();

// ─── Helpers ─────────────────────────────────────────────────────────────────
static async Task EnsureBucketExistsAsync(AmazonS3Client s3, string bucket)
{
    try { await s3.GetBucketLocationAsync(bucket); }
    catch { await s3.PutBucketAsync(bucket); }
}
