namespace BionicproAuth.Api.Dtos;

public class ReportDto
{
    public int ClientId { get; set; }
    public string FullName { get; set; }
    public string Email { get; set; }
    public int TotalSessions { get; set; }
    public int TotalActiveMinutes { get; set; }
    public int TotalSteps { get; set; }
    public decimal AvgBatteryUsage { get; set; }
    public DateTime LastSessionDate { get; set; }
}