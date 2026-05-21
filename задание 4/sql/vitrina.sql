CREATE TABLE default.buyer_summary_report_mv
(
    buyer_id Int64,
    total_orders UInt32,
    total_spent Decimal(18, 2),
    total_discount Decimal(18, 2),
    avg_sensor_value Float64,
    max_power Decimal(18, 2),
    sign_time DateTime
)
ENGINE = ReplacingMergeTree(sign_time)
PRIMARY KEY buyer_id;