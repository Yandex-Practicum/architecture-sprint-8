using BionicproReport.Dtos;

namespace BionicproReport.Services;

public interface IClickHouseReportService
{
    Task<ReportDto?> GetReportByUserIdAsync(uint userId);
}