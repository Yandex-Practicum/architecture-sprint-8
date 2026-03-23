namespace BionicproReport.Services;

public interface IReportStorage
{
    Task<string> GetReportUrlAsync(Guid userId);
    Task GenerateAndStoreReportAsync(Guid userId, Stream reportContent);
    
    Task<string> GetReportUrlAsync(uint userId);
    Task GenerateAndStoreReportAsync(uint userId, Stream reportContent);
    Task<bool> ReportExistsAsync(string key);
    Task<string> GetCurrentTimestampAsync();
}