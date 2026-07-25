namespace report_service.Services;

public interface IS3Service
{
    Task<bool> ExistsAsync(string key);
    Task UploadJsonAsync(string key, object data);
    Task<T> GetJsonAsync<T>(string key);
}