CREATE TABLE IF NOT EXISTS bionicpro.prosthesis_reports_mart (
    user_id String,
    prosthesis_id String,
    recorded_at DateTime,
    movement_type String,
    battery_level Float32,
    crm_user_name String,
    crm_region String
) ENGINE = MergeTree()
ORDER BY (user_id, recorded_at);