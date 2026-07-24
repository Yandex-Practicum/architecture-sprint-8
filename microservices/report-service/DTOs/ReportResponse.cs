using report_service.Models;

namespace report_service.DTOs;

public class ReportResponse
{
    public string UserId { get; set; } = string.Empty;
    public UserReport? Report { get; set; }
    public DateTime GeneratedAt { get; set; }
}