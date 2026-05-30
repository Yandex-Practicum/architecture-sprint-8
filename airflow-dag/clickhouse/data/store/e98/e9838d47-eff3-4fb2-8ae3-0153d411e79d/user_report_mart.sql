ATTACH TABLE _ UUID '3d38e3e0-f289-4ae2-90f2-981aaebc3dfe'
(
    `user_id` String,
    `user_name` String,
    `email` String,
    `phone` String,
    `prosthesis_model` String,
    `serial_number` String,
    `registration_date` Date,
    `total_movements` UInt32 DEFAULT 0,
    `avg_reaction_time` Float32 DEFAULT 0,
    `median_reaction_time` Float32 DEFAULT 0,
    `min_reaction_time` UInt16 DEFAULT 0,
    `max_reaction_time` UInt16 DEFAULT 0,
    `avg_signal_quality` Float32 DEFAULT 0,
    `min_signal_quality` Float32 DEFAULT 0,
    `avg_battery_level` UInt8 DEFAULT 0,
    `performance_score` Float32 DEFAULT 0,
    `needs_calibration` Bool DEFAULT false,
    `last_activity_date` Date,
    `report_date` Date DEFAULT today(),
    `updated_at` DateTime DEFAULT now()
)
ENGINE = TinyLog
