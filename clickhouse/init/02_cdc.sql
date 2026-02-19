-- 1) KafkaEngine table читает топик Debezium
CREATE TABLE IF NOT EXISTS kafka_crm_customers
(
  raw String
)
ENGINE = Kafka
SETTINGS
  kafka_broker_list = 'kafka:29092',
  kafka_topic_list = 'crm.public.customers',
  kafka_group_name = 'ch_cdc_crm_customers',
  kafka_format = 'JSONAsString',
  kafka_num_consumers = 1;

-- 2) Staging таблица под актуальное состояние клиента (upsert через ReplacingMergeTree)
CREATE TABLE IF NOT EXISTS stg_crm_customers
(
  customer_id   String,
  crm_user_id   String,
  full_name     String,
  email         String,
  phone         String,
  country       String,
  city          String,
  prosthesis_id String,
  contract_id   String,
  updated_at    DateTime64(6, 'UTC'),
  op            LowCardinality(String),
  loaded_at     DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (customer_id);

-- 3) MV парсит Debezium envelope и пишет в stg
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_kafka_to_stg_crm_customers
TO stg_crm_customers
AS
SELECT
  JSONExtractString(raw, 'after', 'customer_id')   AS customer_id,
  JSONExtractString(raw, 'after', 'crm_user_id')   AS crm_user_id,
  JSONExtractString(raw, 'after', 'full_name')     AS full_name,
  JSONExtractString(raw, 'after', 'email')         AS email,
  JSONExtractString(raw, 'after', 'phone')         AS phone,
  JSONExtractString(raw, 'after', 'country')       AS country,
  JSONExtractString(raw, 'after', 'city')          AS city,
  JSONExtractString(raw, 'after', 'prosthesis_id') AS prosthesis_id,
  JSONExtractString(raw, 'after', 'contract_id')   AS contract_id,
  parseDateTime64BestEffort(JSONExtractString(raw, 'after', 'updated_at'), 6) AS updated_at,
  JSONExtractString(raw, 'op') AS op,
  now64(3) AS loaded_at
FROM kafka_crm_customers
WHERE JSONExtractString(raw, 'op') IN ('c','u','r')
  AND JSONHas(raw, 'after')
  AND JSONExtractString(raw, 'after', 'customer_id') != '';

-- NOTE: для delete ('d') можно сделать отдельную логику позже, для сдачи не нужно.
