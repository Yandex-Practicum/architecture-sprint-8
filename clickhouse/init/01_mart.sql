CREATE TABLE IF NOT EXISTS stg_crm_customers
(
  customer_id String,
  crm_user_id String,
  full_name String,
  email String,
  phone String,
  country String,
  city String,
  prosthesis_id String,
  contract_id String,
  updated_at DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id);

CREATE TABLE IF NOT EXISTS stg_telemetry_daily
(
  day Date,
  prosthesis_id String,
  samples_count UInt64,
  active_seconds UInt64,
  movements_count UInt64,
  errors_count UInt64,
  avg_battery Float32,
  max_load Float32,
  updated_at DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(day)
ORDER BY (prosthesis_id, day);

CREATE TABLE IF NOT EXISTS mart_user_daily_report
(
  day Date,
  customer_id String,
  prosthesis_id String,
  full_name String,
  email String,
  phone String,
  country String,
  city String,
  contract_id String,
  samples_count UInt64,
  active_seconds UInt64,
  movements_count UInt64,
  errors_count UInt64,
  avg_battery Float32,
  max_load Float32,
  loaded_at DateTime
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (customer_id, day);
