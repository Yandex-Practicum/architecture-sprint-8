"""
BionicPRO CDC Consumer — приём CDC-событий из Kafka (Debezium) в OLAP БД.

Слушает топики Debezium для таблиц crm_data.clients и crm_data.orders,
применяет изменения к CDC-репликам в olap_data и обновляет
Materialized View mv_user_report.

Топики Debezium (формат: {topic.prefix}.{schema}.{table}):
  - cdc.public.clients
  - cdc.public.orders
"""

import json
import logging
import os
import time
from datetime import date, timedelta

import psycopg2
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ----------------------- Config -----------------------

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://airflow:airflow@postgres:5432/olap_data")
TOPICS = ["cdc.public.clients", "cdc.public.orders"]
CONSUMER_GROUP = "cdc-olap-consumer"
BATCH_SIZE = int(os.environ.get("CDC_BATCH_SIZE", "50"))
REFRESH_INTERVAL = int(os.environ.get("CDC_REFRESH_INTERVAL", "5"))


# ----------------------- DB helpers -------------------

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def upsert_client(cur, data):
    """INSERT или UPDATE записи в cdc_clients."""
    cur.execute(
        """
        INSERT INTO cdc_clients (user_id, full_name, email, phone, last_contact_date)
        VALUES (%(user_id)s, %(full_name)s, %(email)s, %(phone)s, %(last_contact_date)s)
        ON CONFLICT (user_id) DO UPDATE SET
            full_name = EXCLUDED.full_name,
            email = EXCLUDED.email,
            phone = EXCLUDED.phone,
            last_contact_date = EXCLUDED.last_contact_date
        """,
        data,
    )


def delete_client(cur, key_data):
    """Удаление записи из cdc_clients."""
    cur.execute("DELETE FROM cdc_clients WHERE user_id = %(user_id)s", key_data)


def upsert_order(cur, data):
    """INSERT или UPDATE записи в cdc_orders."""
    cur.execute(
        """
        INSERT INTO cdc_orders (order_id, client_id, order_status, prosthesis_model, order_date, is_latest)
        VALUES (%(order_id)s, %(client_id)s, %(order_status)s, %(prosthesis_model)s, %(order_date)s, %(is_latest)s)
        ON CONFLICT (order_id) DO UPDATE SET
            client_id = EXCLUDED.client_id,
            order_status = EXCLUDED.order_status,
            prosthesis_model = EXCLUDED.prosthesis_model,
            order_date = EXCLUDED.order_date,
            is_latest = EXCLUDED.is_latest
        """,
        data,
    )


def delete_order(cur, key_data):
    """Удаление записи из cdc_orders."""
    cur.execute("DELETE FROM cdc_orders WHERE order_id = %(order_id)s", key_data)


def refresh_materialized_view(conn):
    """Обновление Materialized View витрины отчётности."""
    with conn.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_user_report")
    conn.commit()
    logger.info("Materialized View mv_user_report обновлён")


# ----------------------- Date conversion ---------------

def convert_epoch_days(value):
    """Debezium передаёт DATE как кол-во дней от epoch (1970-01-01)."""
    if value is None:
        return None
    if isinstance(value, int):
        return (date(1970, 1, 1) + timedelta(days=value)).isoformat()
    return value


def convert_client_dates(data):
    """Конвертация дат в записи клиента."""
    if data is None:
        return data
    data = dict(data)
    data["last_contact_date"] = convert_epoch_days(data.get("last_contact_date"))
    return data


def convert_order_dates(data):
    """Конвертация дат в записи заказа."""
    if data is None:
        return data
    data = dict(data)
    data["order_date"] = convert_epoch_days(data.get("order_date"))
    return data


# ----------------------- Event processing -------------

def process_event(cur, topic, message):
    """Обработка одного CDC-события Debezium."""
    payload = message.get("payload") if "payload" in message else message

    op = payload.get("op")
    after = payload.get("after")
    before = payload.get("before")

    if topic == "cdc.public.clients":
        if op in ("c", "r", "u"):  # create, read (snapshot), update
            upsert_client(cur, convert_client_dates(after))
        elif op == "d":  # delete
            delete_client(cur, before)
    elif topic == "cdc.public.orders":
        if op in ("c", "r", "u"):
            upsert_order(cur, convert_order_dates(after))
        elif op == "d":
            delete_order(cur, before)


# ----------------------- Main loop --------------------

def create_consumer():
    """Создание Kafka consumer с повторными попытками подключения."""
    while True:
        try:
            consumer = KafkaConsumer(
                *TOPICS,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id=CONSUMER_GROUP,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
                key_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
                consumer_timeout_ms=1000,
            )
            logger.info("Подключение к Kafka: %s, топики: %s", KAFKA_BOOTSTRAP, TOPICS)
            return consumer
        except NoBrokersAvailable:
            logger.warning("Kafka недоступна, повтор через 5 сек...")
            time.sleep(5)


def main():
    consumer = create_consumer()
    conn = get_db_connection()
    last_refresh = 0
    processed = 0

    logger.info("CDC Consumer запущен, ожидание событий...")

    while True:
        try:
            batch = consumer.poll(timeout_ms=1000, max_records=BATCH_SIZE)

            if batch:
                cur = conn.cursor()
                for tp, messages in batch.items():
                    for msg in messages:
                        if msg.value is None:
                            continue
                        process_event(cur, msg.topic, msg.value)
                        processed += 1

                conn.commit()
                cur.close()
                consumer.commit()

                now = time.time()
                if now - last_refresh >= REFRESH_INTERVAL:
                    refresh_materialized_view(conn)
                    last_refresh = now
                    logger.info("Обработано %d CDC-событий", processed)
                    processed = 0

        except psycopg2.OperationalError:
            logger.warning("Потеряно соединение с БД, переподключение...")
            try:
                conn.close()
            except Exception:
                pass
            conn = get_db_connection()
        except Exception as e:
            logger.error("Ошибка обработки: %s", e)
            try:
                conn.rollback()
            except Exception:
                pass
            time.sleep(1)


if __name__ == "__main__":
    main()
