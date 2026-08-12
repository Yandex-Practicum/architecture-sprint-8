CREATE DATABASE IF NOT EXISTS reports;

-- Витрина отчётов: одна строка на клиента на каждый обработанный пакет ETL.
-- Наполняется исключительно Airflow DAG (airflow/dags/reports_etl_dag.py) -
-- слой API только читает из этой таблицы, никогда не вычисляет агрегаты на лету.
CREATE TABLE IF NOT EXISTS reports.user_report_mart
(
    customer_id             String,
    report_generated_at     DateTime,
    full_name               String,
    region                  String,
    prosthesis_model        String,
    events_count            UInt32,
    avg_myosignal_quality   Float32,
    avg_recognition_latency_ms Float32,
    min_battery_level       UInt8,
    last_action_recognized  String
)
ENGINE = ReplacingMergeTree(report_generated_at)
ORDER BY (customer_id);
