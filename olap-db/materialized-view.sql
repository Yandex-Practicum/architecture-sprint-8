
-- Материализованное представление, которое обновляет витрину
CREATE MATERIALIZED VIEW emg_user_summary_mv
ENGINE = AggregatingMergeTree()
ORDER BY (user_id)
POPULATE AS
SELECT
    c.id AS user_id,
    c.name,
    c.age,
    c.gender,
    c.email,
    c.country,
    count() AS total_signals,
    avg(toUInt64(signal_duration)) AS avg_signal_duration_sec,
    avg(signal_amplitude) AS avg_signal_amplitude,
    max(signal_frequency) AS max_frequency,
    max(signal_time) AS last_signal_time,
    groupArray(muscle_group) AS muscle_usage_count_raw,
    groupUniqArray(muscle_group) AS unique_muscles_used,
    length(groupArray(muscle_group)) AS muscle_usage_count
FROM emg_sensor_data e
INNER JOIN dim_customers c ON e.user_id = c.id
GROUP BY c.id, c.name, c.age, c.gender, c.email, c.country;