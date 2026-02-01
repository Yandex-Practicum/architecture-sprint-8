import psycopg2
from datetime import datetime, timedelta
import random

def generate_dummy_data():
    """Generate dummy data for CRM and telemetry databases, continuing from last IDs"""

    # CRM Database connection
    crm_conn = psycopg2.connect(
        host="localhost",
        port="5434",
        database="crm_db",
        user="crm_user",
        password="crm_password123"
    )

    # Telemetry Database connection
    telemetry_conn = psycopg2.connect(
        host="localhost",
        port="5435",
        database="telemetry_db",
        user="telemetry_user",
        password="telemetry_password123"
    )

    crm_cursor = crm_conn.cursor()
    telemetry_cursor = telemetry_conn.cursor()

    # === Генерация 5 новых клиентов с уникальными client_id и external_client_id ===
    crm_cursor.execute("SELECT COALESCE(MAX(client_id), 0) FROM clients")
    start_client_id = crm_cursor.fetchone()[0] + 1

    clients = []
    for i in range(5):
        client_id = start_client_id + i
        external_id = f"client_{client_id:03d}"
        first_name = random.choice(["Иван", "Мария", "Алексей", "Екатерина", "Дмитрий"])
        last_name = random.choice(["Петров", "Сидорова", "Иванов", "Смирнова", "Кузнецов"])
        email = f"{external_id}@example.com"  # Уникален по design
        phone = f"+7916{random.randint(1000000, 9999999)}"
        date_of_birth = datetime(1980 + random.randint(0, 20), random.randint(1, 12), random.randint(1, 28))

        clients.append((client_id, external_id, first_name, last_name, email, phone, date_of_birth))

    # Вставка клиентов
    for client in clients:
        crm_cursor.execute("""
            INSERT INTO clients (client_id, external_client_id, first_name, last_name, email, phone, date_of_birth)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (client_id) DO NOTHING
        """, client)

    crm_conn.commit()
    print(f"✅ Added {len(clients)} new clients: {[(c[0], c[1]) for c in clients]}")

    # === Генерация устройств для клиентов (до 2 на клиента) ===
    crm_cursor.execute("SELECT client_id FROM clients WHERE is_active IS TRUE")
    all_client_ids = [row[0] for row in crm_cursor.fetchall()]

    # Получаем следующий номер для device_id
    crm_cursor.execute("""
        SELECT COALESCE(MAX(CAST(SUBSTR(device_id, 8) AS INTEGER)), 0)
        FROM devices
        WHERE device_id ~ '^device_[0-9]{3}$'
    """)
    next_device_num = crm_cursor.fetchone()[0] + 1

    device_types = ['верхняя_конечность', 'нижняя_конечность', 'кисть', 'стопа']
    devices = []

    for client_id in all_client_ids:
        crm_cursor.execute("SELECT COUNT(*) FROM devices WHERE client_id = %s", (client_id,))
        device_count = crm_cursor.fetchone()[0]
        if device_count >= 2:
            continue  # Уже достаточно устройств

        device_id = f"device_{next_device_num:03d}"
        next_device_num += 1

        device_name = random.choice(["Мой протез", "Основной протез", "Запасной протез", "Тестовый протез"])
        device_type = random.choice(device_types)
        serial_number = f"SN-{device_type.upper()[:3]}-{random.randint(1000, 9999)}"
        manufacturing_date = datetime(2023, random.randint(1, 12), random.randint(1, 28))
        activation_date = manufacturing_date + timedelta(days=random.randint(1, 30))

        devices.append((device_id, client_id, device_name, device_type, serial_number, manufacturing_date, activation_date))

    # Вставка устройств
    for device in devices:
        crm_cursor.execute("""
            INSERT INTO devices (device_id, client_id, device_name, device_type, serial_number, manufacturing_date, activation_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (device_id) DO NOTHING
        """, device)

    crm_conn.commit()
    print(f"✅ Added {len(devices)} new devices: {[d[0] for d in devices]}")

    # === Генерация телеметрии для всех устройств ===
    crm_cursor.execute("SELECT device_id FROM devices")
    all_device_ids = [row[0] for row in crm_cursor.fetchall()]

    print(f"📡 Generating telemetry data for {len(all_device_ids)} devices...")
    for device_id in all_device_ids:
        for _ in range(50):
            timestamp = datetime.now() - timedelta(hours=random.randint(0, 72), minutes=random.randint(0, 59))
            battery_level = round(random.uniform(20.0, 100.0), 2)
            temperature = round(random.uniform(20.0, 35.0), 2)
            pressure = round(random.uniform(5.0, 25.0), 4)
            flexion_angle = round(random.uniform(0.0, 90.0), 2)
            step_count = random.randint(0, 500) if device_id.endswith('0') or device_id.endswith('3') else 0
            error_code = random.choices([0, 1, 2], weights=[85, 10, 5])[0]
            accel_x = round(random.uniform(-2.0, 2.0), 4)
            accel_y = round(random.uniform(-2.0, 2.0), 4)
            accel_z = round(random.uniform(-2.0, 2.0), 4)

            telemetry_cursor.execute("""
                INSERT INTO device_telemetry 
                (device_id, timestamp, battery_level, temperature, pressure_sensor_reading, 
                 flexion_angle, step_count, error_code, accelerometer_x, accelerometer_y, accelerometer_z)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (device_id, timestamp, battery_level, temperature, pressure, flexion_angle, step_count, error_code, accel_x, accel_y, accel_z))

    telemetry_conn.commit()
    print(f"✅ Generated {len(all_device_ids) * 50} telemetry records")

    # Закрытие соединений
    crm_cursor.close()
    crm_conn.close()
    telemetry_cursor.close()
    telemetry_conn.close()

    print("\n🎉 Data generation completed successfully!")
    print(f"- New clients: {len(clients)}")
    print(f"- New devices: {len(devices)}")
    print(f"- Telemetry records: {len(all_device_ids) * 50}")

if __name__ == "__main__":
    generate_dummy_data()
