-- Create Kafka engine tables for CDC data
CREATE TABLE crm_clients_queue (
    op String,
    before Nullable(String),
    after String,
    _topic String,
    _partition UInt64,
    _offset UInt64,
    _timestamp DateTime,
    _key String
) ENGINE = Kafka('kafka:29092', 'crm.crm_clients', 'group1', 'JSONEachRow');

CREATE TABLE telemetry_events_queue (
    op String,
    before Nullable(String),
    after String,
    _topic String,
    _partition UInt64,
    _offset UInt64,
    _timestamp DateTime,
    _key String
) ENGINE = Kafka('kafka:29092', 'crm.telemetry_events', 'group1', 'JSONEachRow');

-- Create materialized tables to store the data
CREATE TABLE crm_clients (
    client_id String,
    name String,
    email String
) ENGINE = ReplacingMergeTree()
ORDER BY client_id;

CREATE TABLE telemetry_events (
    id UInt64,
    client_id String,
    event String,
    timestamp DateTime
) ENGINE = MergeTree()
ORDER BY (client_id, timestamp);

-- Create materialized views to populate tables from Kafka
CREATE MATERIALIZED VIEW crm_clients_mv TO crm_clients AS
SELECT
    JSONExtractString(after, 'client_id') AS client_id,
    JSONExtractString(after, 'name') AS name,
    JSONExtractString(after, 'email') AS email
FROM crm_clients_queue
WHERE op IN ('c', 'u');

CREATE MATERIALIZED VIEW telemetry_events_mv TO telemetry_events AS
SELECT
    JSONExtractUInt(after, 'id') AS id,
    JSONExtractString(after, 'client_id') AS client_id,
    JSONExtractString(after, 'event') AS event,
    parseDateTimeBestEffort(JSONExtractString(after, 'timestamp')) AS timestamp
FROM telemetry_events_queue
WHERE op IN ('c', 'u');

-- Create the datamart with Materialized View
CREATE TABLE client_datamart (
    client_id String,
    name String,
    email String,
    total_events UInt64,
    last_event DateTime
) ENGINE = MergeTree()
ORDER BY client_id;