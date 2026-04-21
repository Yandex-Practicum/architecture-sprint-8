namespace bionicpro_report.Models
{
    public class MinioReportResponse
    {
        public string ReportId { get; set; } = string.Empty;
        public string CdnUrl { get; set; } = string.Empty;
        public bool FromCache { get; set; }
        public DateTime GeneratedAt { get; set; }
        public DateTime? CachedUntil { get; set; }
    }
}
