CREATE TABLE IF NOT EXISTS crm_customers_staging
(
    customer_id UInt32,
    keycloak_username String,
    full_name String,
    email String,
    country_code String
)
ENGINE = MergeTree
ORDER BY (keycloak_username, customer_id);

CREATE TABLE IF NOT EXISTS crm_prostheses_staging
(
    prosthesis_id UInt32,
    customer_id UInt32,
    prosthesis_code String,
    model_name String,
    activated_at DateTime
)
ENGINE = MergeTree
ORDER BY (prosthesis_code, customer_id);

CREATE TABLE IF NOT EXISTS telemetry_daily_staging
(
    prosthesis_code String,
    telemetry_from DateTime,
    telemetry_to DateTime,
    total_events UInt64,
    total_active_minutes UInt64,
    total_grip_actions UInt64,
    avg_signal Float64,
    avg_battery_level Float64
)
ENGINE = MergeTree
ORDER BY prosthesis_code;

CREATE TABLE IF NOT EXISTS reports_user_summary
(
    keycloak_username String,
    customer_id UInt32,
    full_name String,
    email String,
    country_code String,
    prosthesis_id UInt32,
    prosthesis_code String,
    model_name String,
    activated_at DateTime,
    telemetry_from DateTime,
    telemetry_to DateTime,
    total_events UInt64,
    total_active_minutes UInt64,
    total_grip_actions UInt64,
    avg_signal Float64,
    avg_battery_level Float64,
    report_generated_at DateTime
)
ENGINE = MergeTree
ORDER BY (keycloak_username, prosthesis_code);
