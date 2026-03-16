namespace BionicproReport.Dtos;

public class ReportDto
{
    public uint UserId { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Email { get; set; } = string.Empty;
    public byte Age { get; set; }
    public string Gender { get; set; } = string.Empty;
    public string Country { get; set; } = string.Empty;
    public string ProsthesisType { get; set; } = string.Empty;
    public uint TotalSessions { get; set; }
    public ulong TotalSignalDuration { get; set; }
    public double AvgSignalFrequency { get; set; }
    public decimal AvgSignalAmplitude { get; set; }
    public DateTime LastSignalTime { get; set; }
    public DateTime UpdatedAt { get; set; }
}