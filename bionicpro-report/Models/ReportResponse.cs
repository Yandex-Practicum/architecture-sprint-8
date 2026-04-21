namespace bionicpro_report.Models
{
    public class ReportResponse
    {
        public string UserId { get; set; } = string.Empty;
        public string UserName { get; set; } = string.Empty;
        public string UserEmail { get; set; } = string.Empty;
        public List<ProsthesisReport> Reports { get; set; } = new();
        public ReportSummary Summary { get; set; } = new();
        public DateTime GeneratedAt { get; set; } = DateTime.UtcNow;
    }
}
