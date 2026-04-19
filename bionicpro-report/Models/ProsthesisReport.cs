namespace bionicpro_report.Models
{
    public class ProsthesisReport
    {
        public string ProsthesisId { get; set; } = string.Empty;
        public string ProsthesisType { get; set; } = string.Empty;
        public DateTime ReportDate { get; set; }
        public double AvgReactionTimeMs { get; set; }
        public uint MaxReactionTimeMs { get; set; }
        public uint MinReactionTimeMs { get; set; }
        public uint TotalSignals { get; set; }
        public uint SuccessfulMovements { get; set; }
        public uint FailedMovements { get; set; }
        public double MisclassificationRate { get; set; }
        public double AvgBatteryLevel { get; set; }
        public int MinBatteryLevel { get; set; }
        public bool QualityOk { get; set; }
        public uint TuningCount { get; set; }
        public DateTime? LastTuningDate { get; set; }
    }
}
