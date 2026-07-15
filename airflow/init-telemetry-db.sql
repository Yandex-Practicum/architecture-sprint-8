CREATE TABLE IF NOT EXISTS telemetry
(
    prosthesis_serial varchar(255),
    movements         int,
    response_ms       int,
    active_seconds    int,
    recorded_at       timestamp DEFAULT now(),
    CONSTRAINT telemetry_pk PRIMARY KEY (prosthesis_serial, recorded_at)
);

INSERT INTO telemetry (prosthesis_serial, movements, response_ms, active_seconds, recorded_at)
VALUES ('05d488c1-da0f-4955-8c1e-07633b524464', 100, 100, 200, current_date - 1 + time '12:00'),
       ('05d488c1-da0f-4955-8c1e-07633b524464', 150, 100, 400, current_date - 1 + time '13:00'),
       ('05d488c1-da0f-4955-8c1e-07633b524464', 150, 120, 300, current_date - 1 + time '14:00'),
       ('4b7d0b00-7ccc-44d2-815c-1a23e6f3ae9e', 100, 150, 100, current_date - 1 + time '15:00'),
       ('4b7d0b00-7ccc-44d2-815c-1a23e6f3ae9e', 200, 150, 150, current_date - 1 + time '16:00'),
       ('cf7ef2c3-fa64-47b5-809d-727dcdf28fa9', 200, 200, 200, current_date - 1 + time '17:00'),
       ('05d488c1-da0f-4955-8c1e-07633b524464', 150, 150, 200, current_date + time '12:00'),
       ('05d488c1-da0f-4955-8c1e-07633b524464', 300, 200, 100, current_date + time '13:00');
