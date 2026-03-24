-- MaterializedView: автоматически переносит данные из Kafka-таблицы
-- в целевую таблицу crm_customers_cdc при поступлении новых сообщений

CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.crm_customers_mv
TO bionicpro.crm_customers_cdc AS
SELECT
    `after.customer_id`  AS customer_id,
    `after.full_name`    AS full_name,
    `after.email`        AS email,
    `after.phone`        AS phone,
    now()                AS created_at
FROM bionicpro.crm_customers_kafka
WHERE `after.customer_id` != '';

-- Витрина отчётности: объединяет CRM-данные (через CDC) с телеметрией.
-- Обновляется автоматически при вставке данных.

CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.user_report_mv
ENGINE = ReplacingMergeTree()
ORDER BY (customer_id, report_date)
POPULATE AS
SELECT
    t.customer_id                         AS customer_id,
    c.full_name                           AS full_name,
    c.email                               AS email,
    toDate(t.event_ts)                    AS report_date,
    count()                               AS total_events,
    round(avg(t.signal_strength), 4)      AS avg_signal_strength,
    round(uniqExact(toHour(t.event_ts)), 1) AS active_hours,
    count()                               AS movement_count
FROM bionicpro.telemetry_events AS t
INNER JOIN bionicpro.crm_customers_cdc AS c
    ON t.customer_id = c.customer_id
GROUP BY
    t.customer_id,
    c.full_name,
    c.email,
    toDate(t.event_ts);
