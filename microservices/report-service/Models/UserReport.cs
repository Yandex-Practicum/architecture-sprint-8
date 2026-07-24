namespace report_service.Models;

public class UserReport
{
    public string UserId { get; set; } = string.Empty;
    public string UserEmail { get; set; } = string.Empty;
    public string UserName { get; set; } = string.Empty;
    public long TotalSteps { get; set; }
    public long TotalActiveMinutes { get; set; }
    public double AvgBattery { get; set; }
    public long ErrorCount { get; set; }
    public DateTime ReportDate { get; set; }
}