-- =============================================================================
-- BionicPRO · ClickHouse · Init Script
-- =============================================================================
-- Создаётся при первом запуске контейнера olap_db.
-- Две таблицы:
--   1. emg_sensor_data   — сырая телеметрия с датчиков (загружается из CSV)
--   2. user_reports       — витрина для сервиса отчётов (заполняется Airflow)
-- =============================================================================

-- ─── 1. Сырая телеметрия ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS emg_sensor_data (
    user_id          UInt32,
    prosthesis_type  String,
    muscle_group     String,
    signal_frequency UInt32,
    signal_duration  UInt32,
    signal_amplitude Decimal(5,2),
    signal_time      DateTime
) ENGINE = MergeTree()
ORDER BY (user_id, prosthesis_type, signal_time);

-- Загрузка начальных данных из CSV (файл монтируется в /var/lib/clickhouse/user_files/)
INSERT INTO emg_sensor_data
SELECT *
FROM file('olap.csv', 'CSV',
    'user_id UInt32,
     prosthesis_type String,
     muscle_group String,
     signal_frequency UInt32,
     signal_duration UInt32,
     signal_amplitude Decimal(5,2),
     signal_time DateTime')
SETTINGS input_format_with_names_use_header = 1;

-- ─── 2. Витрина отчётов ─────────────────────────────────────────────────────
-- Заполняется Airflow DAG (etl_reports) по расписанию @daily.
-- ORDER BY начинается с user_id — основной фильтр при запросе отчёта.

CREATE TABLE IF NOT EXISTS user_reports (
    user_id          UInt32,
    customer_name    String,
    customer_email   String,
    prosthesis_type  String,
    total_signals    UInt64,
    avg_amplitude    Float64,
    avg_frequency    Float64,
    avg_duration     Float64,
    min_signal_time  DateTime,
    max_signal_time  DateTime,
    report_updated   DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (user_id, prosthesis_type);
