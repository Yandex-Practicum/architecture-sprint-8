namespace bionicpro_report.Models
{
    public class ReportSummary
    {
        public double OverallAvgReactionTime { get; set; }
        public double OverallSuccessRate { get; set; }
        public long TotalMovements { get; set; }
        public int DaysWithData { get; set; }
        public string Recommendation { get; set; } = string.Empty;
    }
}
