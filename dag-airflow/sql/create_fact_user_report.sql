-- ==========================================================================
-- Витрина отчётности fact_user_report (ClickHouse)
--
-- Объединяет агрегированную телеметрию датчиков с данными CRM.
-- Партиционирование по месяцу, сортировка по user_id + дате
-- для быстрого доступа к данным по конкретному пользователю.
-- ==========================================================================

CREATE TABLE IF NOT EXISTS fact_user_report
(
    user_id               UInt64        COMMENT 'ID пользователя (FK к CRM)',
    report_date           Date          COMMENT 'Дата отчёта (день)',
    session_count         UInt32        COMMENT 'Количество сессий использования протеза за день',
    avg_wear_time_min     Float64       COMMENT 'Среднее время ношения за сессию (минуты)',
    total_gestures        UInt32        COMMENT 'Общее кол-во распознанных жестов за день',
    avg_myosignal_quality Float64       COMMENT 'Среднее качество миосигнала (0..1)',
    order_status          LowCardinality(Nullable(String))
                                        COMMENT 'Статус заказа из CRM',
    prosthesis_model      LowCardinality(Nullable(String))
                                        COMMENT 'Модель протеза',
    last_contact_date     Nullable(Date)
                                        COMMENT 'Дата последнего обращения клиента в CRM',
    loaded_at             DateTime      DEFAULT now()
                                        COMMENT 'Время загрузки строки'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, report_date)
SETTINGS index_granularity = 8192;
