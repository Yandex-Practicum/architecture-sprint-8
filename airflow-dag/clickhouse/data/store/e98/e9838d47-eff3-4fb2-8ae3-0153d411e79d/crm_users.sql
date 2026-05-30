ATTACH TABLE _ UUID '69c39900-b701-4e8d-aad0-32c5fbeda130'
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
    `inserted_at` DateTime DEFAULT now()
)
ENGINE = TinyLog
