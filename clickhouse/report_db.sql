-- Создание базы данных reports если не существует
CREATE DATABASE IF NOT EXISTS reports
COMMENT 'База данных для отчетов';

-- Создание таблицы device_daily_report
CREATE TABLE IF NOT EXISTS reports.device_daily_report
(
    -- Идентификаторы и метаданные
    client_id          String COMMENT 'ID клиента',
    client_name        String COMMENT 'Имя клиента',
    device_sn          String COMMENT 'Серийный номер протеза',

    -- Метрики производительности
    min_response_speed UInt8 COMMENT 'Минимальное время реакции (милисекунды)',
    max_response_speed UInt8 COMMENT 'Максимальное время реакции (милисекунды)',
    avg_response_speed UInt8 COMMENT 'Среднее время реакции (милисекунды)',

    -- Уровень батареи
    min_battery_level  Float32 COMMENT 'Минимальный уровень батареи (0-100)',
    max_battery_level  Float32 COMMENT 'Максимальный уровень батареи (0-100)',

    -- Статистика
    total_signals      UInt32 COMMENT 'Всего сигналов',
    total_errors       UInt32 COMMENT 'Всего ошибок',

    -- Даты
    report_date        Date COMMENT 'Дата на которую сформирован отчет',
    manufacturing_date Date COMMENT 'Дата производства протеза',
    days_in_use        UInt16 COMMENT 'Дней в использовании',

    -- Технические поля для отслеживания
    created_at         DateTime DEFAULT now() COMMENT 'Время создания записи',
    updated_at         DateTime DEFAULT now() COMMENT 'Время обновления записи'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (report_date, client_id, device_sn)
PRIMARY KEY (report_date, client_id)
SETTINGS
    index_granularity = 8192,
    min_rows_for_wide_part = 1000000,
    min_bytes_for_wide_part = 100000000
COMMENT 'Ежедневные отчеты по протезам';