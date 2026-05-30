CREATE TABLE crm_users_queue (
                                 user_id String,
                                 email String,
                                 full_name String,
                                 phone String,
                                 date_of_birth Int32,
                                 gender String,
                                 address String,
                                 prosthesis_model String,
                                 serial_number String,
                                 firmware_version String,
                                 manufactured_date Int32,
                                 warranty_end_date Int32,
                                 registration_date Int32,
                                 last_active_date Int32,
                                 created_at Int64,
                                 updated_at Int64
) ENGINE = Kafka
      SETTINGS
          kafka_broker_list = 'kafka:9092',
          kafka_topic_list = 'crm.crm.users',
          kafka_group_name = 'clickhouse_consumer',
          kafka_format = 'JSONEachRow',
          kafka_num_consumers = 1,
          kafka_skip_broken_messages = 1000;

CREATE TABLE crm_users (
                           user_id String,
                           email String,
                           full_name String,
                           phone String,
                           date_of_birth Date,
                           gender String,
                           address String,
                           prosthesis_model String,
                           serial_number String,
                           firmware_version String,
                           manufactured_date Date,
                           warranty_end_date Date,
                           registration_date Date,
                           last_active_date Date,
                           created_at DateTime,
                           updated_at DateTime,
                           inserted_at DateTime DEFAULT now()
) ENGINE = TinyLog;

CREATE MATERIALIZED VIEW crm_users_mv
            TO crm_users
AS SELECT
       user_id,
       email,
       full_name,
       phone,
       toDate(toDate('1970-01-01') + date_of_birth) as date_of_birth,
       gender,
       address,
       prosthesis_model,
       serial_number,
       firmware_version,
       toDate(toDate('1970-01-01') + manufactured_date) as manufactured_date,
       toDate(toDate('1970-01-01') + warranty_end_date) as warranty_end_date,
       toDate(toDate('1970-01-01') + registration_date) as registration_date,
       toDate(toDate('1970-01-01') + last_active_date) as last_active_date,
       toDateTime(created_at / 1000) as created_at,
       toDateTime(updated_at / 1000) as updated_at,
       now() as inserted_at
   FROM crm_users_queue
   WHERE user_id IS NOT NULL AND user_id != ''