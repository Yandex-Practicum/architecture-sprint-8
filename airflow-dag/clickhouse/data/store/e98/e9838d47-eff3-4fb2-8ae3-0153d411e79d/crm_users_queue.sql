ATTACH TABLE _ UUID '89e83cb5-b4ff-4a3c-8e23-f9b5a806fa39'
(
    `user_id` String,
    `email` String,
    `full_name` String,
    `phone` String,
    `date_of_birth` Int32,
    `gender` String,
    `address` String,
    `prosthesis_model` String,
    `serial_number` String,
    `firmware_version` String,
    `manufactured_date` Int32,
    `warranty_end_date` Int32,
    `registration_date` Int32,
    `last_active_date` Int32,
    `created_at` Int64,
    `updated_at` Int64
)
ENGINE = Kafka
SETTINGS kafka_broker_list = 'kafka:9092', kafka_topic_list = 'crm.crm.users', kafka_group_name = 'clickhouse_consumer', kafka_format = 'JSONEachRow', kafka_num_consumers = 1, kafka_skip_broken_messages = 1000
