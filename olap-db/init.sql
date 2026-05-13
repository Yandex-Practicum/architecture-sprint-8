-- OLAP Database schema for BionicPRO reporting mart
-- Populated by Airflow ETL DAG (bionicpro_etl_dag)

CREATE TABLE IF NOT EXISTS user_report_mart (
    username          VARCHAR(100)  NOT NULL,
    report_date       DATE          NOT NULL,
    full_name         VARCHAR(200),
    device_serial     VARCHAR(50),
    device_model      VARCHAR(100),
    total_active_hours DECIMAL(10,2) DEFAULT 0,
    avg_battery_level  DECIMAL(5,2)  DEFAULT 0,
    total_steps       BIGINT        DEFAULT 0,
    event_count       INTEGER       DEFAULT 0,
    etl_updated_at    TIMESTAMP     DEFAULT NOW(),
    PRIMARY KEY (username, report_date)
);

CREATE INDEX IF NOT EXISTS idx_mart_username
    ON user_report_mart (username);

CREATE INDEX IF NOT EXISTS idx_mart_date
    ON user_report_mart (report_date DESC);
