using Amazon;
using Amazon.Runtime;
using Amazon.S3;
using Amazon.S3.Model;
using System.Text.Json;

namespace report_service.Services;

public class S3Service : IS3Service
{
    private readonly IAmazonS3 _s3Client;
    private readonly string _bucketName;

    public S3Service(IConfiguration config)
    {
        var accessKey = config["S3:AccessKey"] ?? throw new ArgumentNullException("S3:AccessKey");
        var secretKey = config["S3:SecretKey"] ?? throw new ArgumentNullException("S3:SecretKey");
        var serviceUrl = config["S3:ServiceURL"] ?? throw new ArgumentNullException("S3:ServiceURL");
        _bucketName = config["S3:BucketName"] ?? "bionicpro-reports";

        var credentials = new BasicAWSCredentials(accessKey, secretKey);
        var clientConfig = new AmazonS3Config
        {
            ServiceURL = serviceUrl,
            ForcePathStyle = true,
            UseHttp = true
        };

        _s3Client = new AmazonS3Client(credentials, clientConfig);
    }

    public async Task<bool> ExistsAsync(string key)
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

    public async Task UploadJsonAsync(string key, object data)
    {
        var json = JsonSerializer.Serialize(data, new JsonSerializerOptions { WriteIndented = true });
        var request = new PutObjectRequest
        {
            BucketName = _bucketName,
            Key = key,
            ContentBody = json,
            ContentType = "application/json"
        };

        await _s3Client.PutObjectAsync(request);
    }

    public async Task<T> GetJsonAsync<T>(string key)
    {
        var response = await _s3Client.GetObjectAsync(_bucketName, key);
        using var reader = new StreamReader(response.ResponseStream);
        var json = await reader.ReadToEndAsync();

        return JsonSerializer.Deserialize<T>(json) ?? throw new InvalidOperationException($"Failed to deserialize {key}");
    }
}