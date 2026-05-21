namespace bionicpro_reports.models
{
    public class BuyerSummaryReport
    {
        public long BuyerId { get; set; }

        public int TotalOrders { get; set; }

        public decimal TotalSpent { get; set; }

        public decimal TotalDiscount { get; set; }

        public decimal AvgSensorValue { get; set; }

        public decimal MaxPower { get; set; }
    }
}
