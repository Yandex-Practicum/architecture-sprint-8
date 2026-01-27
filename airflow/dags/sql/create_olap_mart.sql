CREATE DATABASE IF NOT EXISTS reports_db;

USE reports_db;

CREATE TABLE IF NOT EXISTS user_reports_mart
(
    user_id String,
    username String,
    prosthesis_id String,
    date Date,
    total_movements UInt32,
    avg_reaction_time Float32,
    min_reaction_time Float32,
    max_reaction_time Float32,
    customer_name String,
    customer_email String,
    order_date Date,
    prosthesis_type String
)
ENGINE = MergeTree()
ORDER BY (user_id, date)
PARTITION BY toYYYYMM(date);

CREATE TABLE IF NOT EXISTS etl_watermark
(
    last_processed_date Date,
    updated_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
ORDER BY updated_at;

INSERT INTO etl_watermark (last_processed_date) VALUES ('1970-01-01');
