CREATE DATABASE telemetry;

\c telemetry;

CREATE TABLE measurements (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  timestamp TIMESTAMPTZ NOT NULL,
  username VARCHAR(255) NOT NULL,
  device_id BIGINT NOT NULL,
  type VARCHAR(255) NOT NULL,
  value FLOAT
);

CREATE TABLE online_devices (
  username VARCHAR(255) NOT NULL,
  device_id INT NOT NULL
);

COPY online_devices FROM '/docker-entrypoint-initdb.d/data/crm_person_devices.csv'  WITH (FORMAT csv, HEADER true);

GRANT ALL PRIVILEGES ON DATABASE telemetry TO airflow;

CREATE DATABASE crm;

\c crm;

CREATE TABLE persons (
  username VARCHAR(255) NOT NULL,
  first_name VARCHAR(255) NOT NULL,
  last_name VARCHAR(255) NOT NULL,
  dob DATE NOT NULL,
  gender VARCHAR(255) NOT NULL,
  profession VARCHAR(255)
);

CREATE TABLE devices (
  id BIGINT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  category VARCHAR(255) NOT NULL
);

CREATE TABLE person_devices (
  owner VARCHAR(255) NOT NULL,
  device_id BIGINT
);

COPY persons FROM '/docker-entrypoint-initdb.d/data/crm_persons.csv'  WITH (FORMAT csv, HEADER true);;
COPY devices FROM '/docker-entrypoint-initdb.d/data/crm_devices.csv'  WITH (FORMAT csv, HEADER true);;
COPY person_devices FROM '/docker-entrypoint-initdb.d/data/crm_person_devices.csv'  WITH (FORMAT csv, HEADER true);

GRANT ALL PRIVILEGES ON DATABASE crm TO airflow;

CREATE DATABASE dwh;

\c dwh;

CREATE TABLE user_daily_measurements (
  username VARCHAR(255) NOT NULL,
  type VARCHAR(255) NOT NULL,
  device_id BIGINT NOT NULL,
  avg_value NUMERIC(10, 3)
);

CREATE UNIQUE INDEX uidx_user_daily_measurements_username_type ON user_daily_measurements(username, type, device_id);

CREATE TABLE actual_persons (
  username VARCHAR(255) NOT NULL,
  first_name VARCHAR(255) NOT NULL,
  last_name VARCHAR(255) NOT NULL,
  gender VARCHAR(255) NOT NULL,
  age INT,
  profession VARCHAR(255),
  device_id BIGINT,
  device_name VARCHAR(255)
);

CREATE UNIQUE INDEX uidx_actual_persons_username ON actual_persons(username, device_id);

CREATE TABLE user_daily_report (
  username VARCHAR(255) NOT NULL,
  day DATE NOT NULL,
  first_name VARCHAR(255) NOT NULL,
  last_name VARCHAR(255) NOT NULL,
  gender VARCHAR(255) NOT NULL,
  age INT,
  profession VARCHAR(255),
  device_id BIGINT,
  device_name VARCHAR(255),
  avg_tension NUMERIC(10, 3),
  avg_impedance NUMERIC(10, 3),
  avg_battery_level NUMERIC(10, 3)
);

CREATE UNIQUE INDEX uidx_user_daily_report_username_day ON user_daily_report(username, day, device_id);

GRANT ALL PRIVILEGES ON DATABASE dwh TO airflow;