CREATE TABLE IF NOT EXISTS telemetry_data (
                                              id SERIAL PRIMARY KEY,
                                              user_id INT NOT NULL,
                                              status VARCHAR(50),
    battery_level INT,
    motor_cycles INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

INSERT INTO telemetry_data (user_id, status, battery_level, motor_cycles, timestamp) VALUES
                                                                                         (1, 'ACTIVE', 80, 1500, NOW() - INTERVAL '2 days'),
                                                                                         (1, 'ACTIVE', 45, 1550, NOW() - INTERVAL '1 day'),
                                                                                         (1, 'CHARGING', 100, 1550, NOW()),

                                                                                         (2, 'ERROR', 15, 3200, NOW() - INTERVAL '5 hours'),
                                                                                         (2, 'INACTIVE', 10, 3200, NOW() - INTERVAL '1 hour'),

                                                                                         (3, 'ACTIVE', 95, 500, NOW() - INTERVAL '10 minutes');