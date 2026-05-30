ATTACH MATERIALIZED VIEW _ UUID '15f0f717-14b7-4208-93c6-9f77a562cc1f' TO reports_db.crm_users
(
    `user_id` String,
    `email` String,
    `full_name` String,
    `phone` String,
    `date_of_birth` Date,
    `gender` String,
    `address` String,
    `prosthesis_model` String,
    `serial_number` String,
    `firmware_version` String,
    `manufactured_date` Date,
    `warranty_end_date` Date,
    `registration_date` Date,
    `last_active_date` Date,
    `created_at` DateTime,
    `updated_at` DateTime,
    `inserted_at` DateTime
) AS
SELECT
    user_id,
    email,
    full_name,
    phone,
    toDate(toDate('1970-01-01') + date_of_birth) AS date_of_birth,
    gender,
    address,
    prosthesis_model,
    serial_number,
    firmware_version,
    toDate(toDate('1970-01-01') + manufactured_date) AS manufactured_date,
    toDate(toDate('1970-01-01') + warranty_end_date) AS warranty_end_date,
    toDate(toDate('1970-01-01') + registration_date) AS registration_date,
    toDate(toDate('1970-01-01') + last_active_date) AS last_active_date,
    toDateTime(created_at / 1000) AS created_at,
    toDateTime(updated_at / 1000) AS updated_at,
    now() AS inserted_at
FROM reports_db.crm_users_queue
WHERE (user_id IS NOT NULL) AND (user_id != '')
