CREATE TABLE IF NOT EXISTS bionicpro.kafka_crm_customer_plan_queue
(
    raw String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.customer_plan',
    kafka_group_name = 'clickhouse_crm_consumer',
    kafka_format = 'JSONAsString';

CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.crm_customer_plan_kafka_mv
TO bionicpro.crm_customer_plan
AS
SELECT
    if(
        JSONHas(raw, 'payload', 'after'),
        JSONExtractString(raw, 'payload', 'after', 'user_id'),
        JSONExtractString(raw, 'after', 'user_id')
    ) AS user_id,
    if(
        JSONHas(raw, 'payload', 'after'),
        JSONExtractString(raw, 'payload', 'after', 'plan_code'),
        JSONExtractString(raw, 'after', 'plan_code')
    ) AS plan_code,
    if(
        if(
            JSONHas(raw, 'payload', 'ts_ms'),
            JSONExtractUInt(raw, 'payload', 'ts_ms'),
            JSONExtractUInt(raw, 'ts_ms')
        ) = 0,
        now64(3),
        fromUnixTimestamp64Milli(
            if(
                JSONHas(raw, 'payload', 'ts_ms'),
                JSONExtractUInt(raw, 'payload', 'ts_ms'),
                JSONExtractUInt(raw, 'ts_ms')
            )
        )
    ) AS updated_at
FROM bionicpro.kafka_crm_customer_plan_queue
WHERE if(
        JSONHas(raw, 'payload', 'op'),
        JSONExtractString(raw, 'payload', 'op'),
        JSONExtractString(raw, 'op')
    ) IN ('c', 'u', 'r')
  AND (JSONHas(raw, 'payload', 'after') OR JSONHas(raw, 'after'))
  AND length(
        if(
            JSONHas(raw, 'payload', 'after'),
            JSONExtractString(raw, 'payload', 'after', 'user_id'),
            JSONExtractString(raw, 'after', 'user_id')
        )
    ) > 0;
