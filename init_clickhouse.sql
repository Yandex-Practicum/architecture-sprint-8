CREATE DATABASE IF NOT EXISTS crm_raw;
CREATE DATABASE IF NOT EXISTS crm_dds;
CREATE DATABASE IF NOT EXISTS crm_report;

CREATE TABLE IF NOT EXISTS crm_raw.crm_users_kafka
(
    user_id UInt32,
    username String,
    email String,
    full_name Nullable(String),

    __op Nullable(String),
    __source_ts_ms Nullable(UInt64),
    __deleted Nullable(String)
    )
    ENGINE = Kafka
    SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.crm_users',
    kafka_group_name = 'clickhouse_crm_users_consumer',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_handle_error_mode = 'stream',
    kafka_skip_broken_messages = 100;

CREATE TABLE IF NOT EXISTS crm_dds.crm_users
(
    user_id UInt32,
    username String,
    email String,
    full_name Nullable(String),

    is_deleted UInt8,
    version UInt64,
    operation LowCardinality(String)
    )
    ENGINE = ReplacingMergeTree(version)
    ORDER BY user_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS crm_raw.crm_users_mv
TO crm_dds.crm_users
AS
SELECT
    user_id,
    username,
    email,
    full_name,

    if(
            lower(ifNull(__deleted, 'false')) = 'true' OR ifNull(__op, '') = 'd',
            1,
            0
    ) AS is_deleted,

    ifNull(
            __source_ts_ms,
            toUInt64(toUnixTimestamp64Milli(now64(3)))
    ) AS version,

    ifNull(__op, '') AS operation
FROM crm_raw.crm_users_kafka;

CREATE TABLE IF NOT EXISTS crm_raw.orders_kafka
(
    order_id UInt64,
    user_id UInt32,
    order_number String,
    product_name String,
    quantity UInt32,
    amount Decimal(18, 2),
    status String,
    created_at Nullable(DateTime64(3)),
    updated_at Nullable(DateTime64(3)),

    __op Nullable(String),
    __source_ts_ms Nullable(UInt64),
    __deleted Nullable(String)
    )
    ENGINE = Kafka
    SETTINGS
    kafka_broker_list = 'kafka:29092',
    kafka_topic_list = 'crm.public.orders',
    kafka_group_name = 'clickhouse_orders_consumer',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 1,
    kafka_handle_error_mode = 'stream',
    kafka_skip_broken_messages = 100;

CREATE TABLE IF NOT EXISTS crm_dds.orders
(
    order_id UInt64,
    user_id UInt32,
    order_number String,
    product_name String,
    quantity UInt32,
    amount Decimal(18, 2),
    status String,
    created_at Nullable(DateTime64(3)),
    updated_at Nullable(DateTime64(3)),

    is_deleted UInt8,
    version UInt64,
    operation LowCardinality(String)
    )
    ENGINE = ReplacingMergeTree(version)
    ORDER BY order_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS crm_raw.orders_mv
TO crm_dds.orders
AS
SELECT
    order_id,
    user_id,
    order_number,
    product_name,
    quantity,
    amount,
    status,
    created_at,
    updated_at,

    if(
            lower(ifNull(__deleted, 'false')) = 'true' OR ifNull(__op, '') = 'd',
            1,
            0
    ) AS is_deleted,

    ifNull(
            __source_ts_ms,
            toUInt64(toUnixTimestamp64Milli(now64(3)))
    ) AS version,

    ifNull(__op, '') AS operation
FROM crm_raw.orders_kafka;

CREATE TABLE IF NOT EXISTS crm_report.user_orders_report
(
    order_id UInt64,
    user_id UInt32,
    username String,
    user_email String,
    full_name Nullable(String),
    order_number String,
    product_name String,
    quantity UInt32,
    amount Decimal(18, 2),
    order_status String,
    order_created_at Nullable(DateTime64(3)),
    version UInt64
    )
    ENGINE = ReplacingMergeTree(version)
    ORDER BY order_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS crm_report.user_orders_report_mv
TO crm_report.user_orders_report
AS
SELECT
    o.order_id AS order_id,
    o.user_id AS user_id,
    u.username AS username,
    u.email AS user_email,
    u.full_name AS full_name,
    o.order_number AS order_number,
    o.product_name AS product_name,
    o.quantity AS quantity,
    o.amount AS amount,
    o.status AS order_status,
    o.created_at AS order_created_at,
    greatest(o.version, u.version) AS version
FROM crm_dds.orders AS o
         LEFT JOIN crm_dds.crm_users AS u
                   ON u.user_id = o.user_id
WHERE o.is_deleted = 0
  AND ifNull(u.is_deleted, 0) = 0;

CREATE VIEW IF NOT EXISTS crm_report.v_user_orders_report AS
SELECT
    order_id,
    user_id,
    username,
    user_email,
    full_name,
    order_number,
    product_name,
    quantity,
    amount,
    order_status,
    order_created_at
FROM crm_report.user_orders_report FINAL;