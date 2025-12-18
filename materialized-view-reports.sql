
CREATE DATABASE IF NOT EXISTS bionicpro;

USE bionicpro;

CREATE TABLE IF NOT EXISTS bionicpro.user_reports_realtime (
    user_id UInt32,
    report_date Date,
    total_signals UInt32,
    avg_duration Float64,
    muscle_groups String,
    session_count UInt32,
    avg_accuracy Float64,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree() 
ORDER BY (user_id, report_date);

INSERT INTO bionicpro.user_reports_realtime (user_id, report_date, total_signals, avg_duration, muscle_groups, session_count, avg_accuracy) VALUES
(1, '2024-01-15', 12, 2850.5, 'Quadriceps,Biceps,Gastrocnemius', 8, 0.89),
(1, '2024-01-16', 15, 3200.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings', 10, 0.92),
(1, '2024-01-17', 18, 3100.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings,Triceps', 12, 0.88),
(1, '2024-01-18', 14, 2950.0, 'Quadriceps,Biceps,Gastrocnemius', 9, 0.91),
(1, '2024-01-19', 16, 3300.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings', 11, 0.87),

(2, '2024-01-15', 9, 3321.67, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings,Triceps', 6, 0.85),
(2, '2024-01-16', 11, 3450.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings', 7, 0.88),
(2, '2024-01-17', 13, 3180.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings,Triceps', 8, 0.90),
(2, '2024-01-18', 10, 3600.0, 'Quadriceps,Biceps,Gastrocnemius', 6, 0.86),
(2, '2024-01-19', 12, 3400.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings', 7, 0.89),

(3, '2024-01-15', 20, 2800.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings,Triceps', 15, 0.93),
(3, '2024-01-16', 22, 2750.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings,Triceps', 16, 0.94),
(3, '2024-01-17', 19, 2900.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings', 14, 0.92),
(3, '2024-01-18', 21, 2850.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings,Triceps', 15, 0.91),
(3, '2024-01-19', 23, 2700.0, 'Quadriceps,Biceps,Gastrocnemius,Hamstrings,Triceps', 17, 0.95);
