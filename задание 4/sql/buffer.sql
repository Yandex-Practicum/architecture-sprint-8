CREATE TABLE default.kafka_sales_queue
(
    payload Tuple(
        before Tuple(id Nullable(Int64), buyer_id Nullable(Int64), total Nullable(Decimal(18,2)), discount Nullable(Decimal(18,2))),
        after Tuple(id Int64, buyer_id Int64, total Decimal(18,2), discount Decimal(18,2)),
        op String
    )
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:29092',
         kafka_topic_list = 'crm.public.sales',
         kafka_group_name = 'ch_sales_consumer',
         kafka_format = 'JSONEachRow';
