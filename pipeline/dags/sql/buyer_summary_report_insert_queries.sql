INSERT INTO buyer_summary_report (
    buyer_id, 
    total_orders, 
    total_spent, 
    total_discount, 
    avg_sensor_value, 
    max_power
)
WITH aggregated_sales AS (
    SELECT 
        buyer_id,
        COUNT(id) AS total_orders,
        SUM(total) AS total_spent,
        SUM(discount) AS total_discount
    FROM sales
    GROUP BY buyer_id
),
aggregated_telemetry AS (
    SELECT 
        buyer_id,
        AVG(value) AS avg_sensor_value,
        MAX(power) AS max_power
    FROM telemetry
    GROUP BY buyer_id
)
SELECT 
    COALESCE(s.buyer_id, t.buyer_id) AS buyer_id,
    COALESCE(s.total_orders, 0),
    COALESCE(s.total_spent, 0.00),
    COALESCE(s.total_discount, 0.00),
    COALESCE(t.avg_sensor_value, 0.00),
    COALESCE(t.max_power, 0.00)
FROM aggregated_sales s
FULL OUTER JOIN aggregated_telemetry t ON s.buyer_id = t.buyer_id;