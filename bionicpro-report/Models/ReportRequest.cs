namespace bionicpro_report.Models
{
    public class ReportRequest
    {
        public string UserId { get; set; } = string.Empty;
        public DateTime? StartDate { get; set; }
        public DateTime? EndDate { get; set; }
        public int Limit { get; set; } = 30;
    }
}
