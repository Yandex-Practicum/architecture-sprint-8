using Amazon.S3;
using Amazon.S3.Model;

namespace BionicproReport.Services;

public class S3ReportStorage : IReportStorage
{
    private readonly IAmazonS3 _s3Client;
    private readonly string _bucketName;
    private readonly string _cdnBaseUrl;
    private readonly ILogger<S3ReportStorage> _logger;
    private string _currentTimestamp;
    private DateTime _lastTimestampCheck = DateTime.MinValue;
    private readonly TimeSpan _timestampCacheDuration = TimeSpan.FromMinutes(5);
    private readonly SemaphoreSlim _timestampLock = new(1, 1);

    public S3ReportStorage(IConfiguration config, ILogger<S3ReportStorage> logger)
    {
        var s3Config = config.GetSection("S3");
        var endpoint = s3Config["Endpoint"];
        var accessKey = s3Config["AccessKey"];
        var secretKey = s3Config["SecretKey"];
        _bucketName = s3Config["BucketName"];
        _cdnBaseUrl = config["Cdn:BaseUrl"];

        var s3ClientConfig = new AmazonS3Config
        {
            ServiceURL = endpoint,
            ForcePathStyle = true,
            AuthenticationRegion = s3Config["Region"]
        };
        _s3Client = new AmazonS3Client(accessKey, secretKey, s3ClientConfig);
        _logger = logger;
    }

    private async Task<string> GetLatestTimestampAsync()
    {
        if (!string.IsNullOrEmpty(_currentTimestamp) && DateTime.UtcNow - _lastTimestampCheck < _timestampCacheDuration)
            return _currentTimestamp;

        await _timestampLock.WaitAsync();
        try
        {
            if (!string.IsNullOrEmpty(_currentTimestamp) && DateTime.UtcNow - _lastTimestampCheck < _timestampCacheDuration)
                return _currentTimestamp;

            var request = new GetObjectRequest
            {
                BucketName = _bucketName,
                Key = "latest.txt"
            };
            try
            {
                using var response = await _s3Client.GetObjectAsync(request);
                using var reader = new StreamReader(response.ResponseStream);
                _currentTimestamp = (await reader.ReadToEndAsync()).Trim();
                _lastTimestampCheck = DateTime.UtcNow;
                _logger.LogInformation("Updated latest timestamp: {Timestamp}", _currentTimestamp);
            }
            catch (AmazonS3Exception ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
            {
                _currentTimestamp = "0";
                _lastTimestampCheck = DateTime.UtcNow;
                _logger.LogWarning("latest.txt not found, using default 0");
            }
            return _currentTimestamp;
        }
        finally { _timestampLock.Release(); }
    }

    public async Task<string> GetCurrentTimestampAsync() => await GetLatestTimestampAsync();

    public async Task<string> GetReportUrlAsync(Guid userId)
    {
        var timestamp = await GetLatestTimestampAsync();
        var key = $"{timestamp}/{userId}.pdf";
        return await ReportExistsAsync(key) ? $"{_cdnBaseUrl}/{key}" : null;
    }

    public async Task<bool> ReportExistsAsync(string key)
    {
        try
        {
            await _s3Client.GetObjectMetadataAsync(_bucketName, key);
            return true;
        }
        catch (AmazonS3Exception ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
        {
            return false;
        }
    }

    public async Task GenerateAndStoreReportAsync(Guid userId, Stream reportContent)
    {
        var timestamp = await GetLatestTimestampAsync();
        var key = $"{timestamp}/{userId}.pdf";
        var request = new PutObjectRequest
        {
            BucketName = _bucketName,
            Key = key,
            InputStream = reportContent,
            ContentType = "application/pdf"
        };
        await _s3Client.PutObjectAsync(request);
        _logger.LogInformation("Report stored at {Key}", key);
    }
}