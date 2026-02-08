#!/bin/bash
# ============================================================================
# BionicPRO Data Seeding Script
# ============================================================================
# Скрипт для заполнения источников данных (CRM и Telemetry PostgreSQL)
# тестовыми данными для указанного пользователя Keycloak
#
# Использование:
#   ./seed-user-data.sh <user_external_id> [customer_id] [full_name] [email] [country]
#
# Примеры:
#   ./seed-user-data.sh cbbbd1f1-ab80-4661-9be6-e9659d9fb277
#   ./seed-user-data.sh "abc-123-def" 2 "Jane Smith" "jane@example.com" "KZ"
#
# Примечание:
#   Данные вставляются только в источники (PostgreSQL)
#   Для загрузки в ClickHouse необходимо запустить Airflow DAG
# ============================================================================

set -e

# ============================================================================
# ПАРАМЕТРЫ
# ============================================================================

USER_ID="${1:-cbbbd1f1-ab80-4661-9be6-e9659d9fb277}"
CUSTOMER_ID="${2:-1}"
FULL_NAME="${3:-Test User}"
EMAIL="${4:-testuser@example.com}"
COUNTRY="${5:-RU}"

echo "============================================================================"
echo "BionicPRO Data Seeding"
echo "============================================================================"
echo "User External ID: $USER_ID"
echo "Customer ID:      $CUSTOMER_ID"
echo "Full Name:        $FULL_NAME"
echo "Email:            $EMAIL"
echo "Country:          $COUNTRY"
echo "============================================================================"
echo ""

# ============================================================================
# 1. CRM DATABASE - CUSTOMERS
# ============================================================================

echo "==> [1/3] Вставка клиента в CRM..."

docker exec -i crm_db psql -U crm_user -d crm_db <<EOF
-- Вставка или обновление клиента
INSERT INTO crm.customers (
    customer_id,
    user_external_id,
    full_name,
    email,
    phone,
    country,
    created_at,
    updated_at
)
VALUES (
    $CUSTOMER_ID,
    '$USER_ID',
    '$FULL_NAME',
    '$EMAIL',
    '+7-900-000-00-01',
    '$COUNTRY',
    NOW() - INTERVAL '60 days',
    NOW()
)
ON CONFLICT (customer_id) DO UPDATE SET
    user_external_id = EXCLUDED.user_external_id,
    full_name = EXCLUDED.full_name,
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    country = EXCLUDED.country,
    updated_at = NOW();

-- Проверка вставки
SELECT 
    customer_id,
    user_external_id,
    full_name,
    email,
    country
FROM crm.customers
WHERE customer_id = $CUSTOMER_ID;
EOF

echo "Клиент добавлен в CRM"
echo ""

# ============================================================================
# 2. CRM DATABASE - PROSTHESES
# ============================================================================

echo "==> [2/3] Вставка протезов в CRM..."

docker exec -i crm_db psql -U crm_user -d crm_db <<EOF
-- Протез 1: BP-ARM-X (рука)
INSERT INTO crm.prostheses (
    prosthesis_id,
    customer_id,
    model,
    activated_at,
    deactivated_at,
    updated_at
)
VALUES (
    101,
    $CUSTOMER_ID,
    'BP-ARM-X',
    NOW() - INTERVAL '40 days',
    NULL,
    NOW()
)
ON CONFLICT (prosthesis_id) DO UPDATE SET
    customer_id = EXCLUDED.customer_id,
    model = EXCLUDED.model,
    updated_at = NOW();

-- Протез 2: BP-LEG-Z (нога)
INSERT INTO crm.prostheses (
    prosthesis_id,
    customer_id,
    model,
    activated_at,
    deactivated_at,
    updated_at
)
VALUES (
    102,
    $CUSTOMER_ID,
    'BP-LEG-Z',
    NOW() - INTERVAL '20 days',
    NULL,
    NOW()
)
ON CONFLICT (prosthesis_id) DO UPDATE SET
    customer_id = EXCLUDED.customer_id,
    model = EXCLUDED.model,
    updated_at = NOW();

-- Проверка вставки
SELECT 
    prosthesis_id,
    customer_id,
    model,
    activated_at,
    CASE WHEN deactivated_at IS NULL THEN 'Активен' ELSE 'Деактивирован' END as status
FROM crm.prostheses
WHERE customer_id = $CUSTOMER_ID
ORDER BY prosthesis_id;
EOF

echo "Протезы добавлены в CRM"
echo ""

# ============================================================================
# 3. TELEMETRY DATABASE - EVENTS
# ============================================================================

echo "==> [3/3] Генерация событиий телеметрии..."

docker exec -i telemetry_db psql -U telemetry_user -d telemetry_db <<EOF
-- Генерация событий телеметрии за последние 7 дней
-- Для каждого протеза создается ~30 событий в день

DO \$\$
DECLARE
    d INT;              -- День (0-6, где 0 = сегодня)
    i INT;              -- Номер события в дне
    ts TIMESTAMPTZ;     -- Временная метка события
    resp_ms DOUBLE PRECISION;   -- Время отклика
    err BOOLEAN;        -- Флаг ошибки
    batt DOUBLE PRECISION;      -- Уровень батареи
BEGIN
    -- Генерация событий для протеза 101 (BP-ARM-X)
    FOR d IN 0..6 LOOP
        -- Начало дня в 08:00
        ts := date_trunc('day', NOW() - make_interval(days => d)) + INTERVAL '08:00:00';
        
        FOR i IN 1..30 LOOP
            -- Случайные метрики с реалистичными значениями
            resp_ms := 50 + random() * 50;           -- 50-100ms (целевое < 100ms)
            err := random() < 0.05;                   -- 5% ошибок
            batt := 30 + random() * 70;               -- 30-100% заряда
            
            INSERT INTO telemetry.events (
                prosthesis_id,
                event_time,
                response_ms,
                is_error,
                battery_level,
                created_at
            )
            VALUES (
                101,
                ts + (i || ' minutes')::interval,
                resp_ms,
                err,
                batt,
                NOW()
            );
        END LOOP;
    END LOOP;
    
    -- Генерация событий для протеза 102 (BP-LEG-Z)
    FOR d IN 0..6 LOOP
        ts := date_trunc('day', NOW() - make_interval(days => d)) + INTERVAL '08:00:00';
        
        FOR i IN 1..30 LOOP
            resp_ms := 50 + random() * 50;
            err := random() < 0.05;
            batt := 30 + random() * 70;
            
            INSERT INTO telemetry.events (
                prosthesis_id,
                event_time,
                response_ms,
                is_error,
                battery_level,
                created_at
            )
            VALUES (
                102,
                ts + (i || ' minutes')::interval,
                resp_ms,
                err,
                batt,
                NOW()
            );
        END LOOP;
    END LOOP;
    
    RAISE NOTICE 'Сгенерировано событий: %', (7 * 30 * 2);
END \$\$;

-- Статистика по событиям
SELECT 
    prosthesis_id,
    DATE(event_time) as event_date,
    COUNT(*) as events_count,
    ROUND(AVG(response_ms)::numeric, 2) as avg_response_ms,
    SUM(CASE WHEN is_error THEN 1 ELSE 0 END) as errors,
    ROUND(AVG(battery_level)::numeric, 2) as avg_battery
FROM telemetry.events
WHERE prosthesis_id IN (101, 102)
GROUP BY prosthesis_id, DATE(event_time)
ORDER BY prosthesis_id, event_date DESC
LIMIT 14;
EOF

echo "События телеметрии сгенерированы"
echo ""