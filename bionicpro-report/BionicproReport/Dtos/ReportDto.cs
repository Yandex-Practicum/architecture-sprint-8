namespace BionicproReport.Dtos;

public class ReportDto
{
    public Guid  ClientId { get; set; }
    public string FullName { get; set; }
    public string Email { get; set; }
    public int TotalSessions { get; set; }
    public int TotalActiveMinutes { get; set; }
    public int TotalSteps { get; set; }
    public decimal AvgBatteryUsage { get; set; }
    public DateOnly LastSessionDate { get; set; }
}