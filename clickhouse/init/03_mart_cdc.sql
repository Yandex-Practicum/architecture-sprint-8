--  витрина отчётов
CREATE VIEW IF NOT EXISTS mart_user_daily_report_cdc AS
SELECT
  t.day,
  t.customer_id,
  coalesce(c.prosthesis_id, t.prosthesis_id) AS prosthesis_id,

  -- CRM поля берём из CDC staging
  c.full_name,
  c.email,
  c.phone,
  c.country,
  c.city,
  c.contract_id,

  -- телеметрия 
  t.samples_count,
  t.active_seconds,
  t.movements_count,
  t.errors_count,
  t.avg_battery,
  t.max_load,


  greatest(t.loaded_at, c.loaded_at) AS loaded_at
FROM mart_user_daily_report t
LEFT JOIN
(
  SELECT
    customer_id,
    anyLast(crm_user_id) AS crm_user_id,
    anyLast(full_name) AS full_name,
    anyLast(email) AS email,
    anyLast(phone) AS phone,
    anyLast(country) AS country,
    anyLast(city) AS city,
    anyLast(prosthesis_id) AS prosthesis_id,
    anyLast(contract_id) AS contract_id,
    max(updated_at) AS updated_at,
    max(loaded_at) AS loaded_at
  FROM stg_crm_customers
  GROUP BY customer_id
) c
ON c.customer_id = t.customer_id;
