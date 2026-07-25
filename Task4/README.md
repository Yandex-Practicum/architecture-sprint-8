# Задание 4. Повышение оперативности и стабильности работы CRM

В docker-compose добавлены:

1. crm-db как источник данных

```
crm-db:
    image: postgres:14
    container_name: crm-db
    environment:
      POSTGRES_DB: crm
      POSTGRES_USER: crm_user
      POSTGRES_PASSWORD: crm_password
    volumes:
      - ./crm_data:/var/lib/postgresql/data
    ports:
      - "5434:5432"
    networks:
      - bionic-network
    restart: unless-stopped
```

2. Для kafka:
- zookeeper
- kafka
- kafka (с Debezium)

Сконфигурирован [Debezium-коннектор](https://github.com/tammaco/architecture-pro-bionicpro/debezium/crm-connector.json).

В [скрипт] (https://github.com/tammaco/architecture-pro-bionicpro/db/init-clickhouse-db.sql) добавлены таблицы для Kafka Engine для приёма данных из CRM и Materialized View для автоматического обновления.

Для чтения данных не из файлов csv, а из ClickHouse, шаг extract_crm в [DAG] (https://github.com/tammaco/architecture-pro-bionicpro/airflow/dags/user_report.py) нужно заменить на фрагмент:

```
def extract_crm_from_ch(**context):
    from clickhouse_driver import Client
    client = Client(host='clickhouse', port=9000, database='bionicpro')
    rows = client.execute("SELECT user_id, user_name, user_email, phone, region, prosthesis_model, purchase_date FROM crm_clients")
    data = [dict(zip(['user_id', 'user_name', 'user_email', 'phone', 'region', 'prosthesis_model', 'purchase_date'], row)) for row in rows]
    context['task_instance'].xcom_push(key='crm_data', value=data)
```


Запуск коннеткора:

1. Поднять сервисы
```
docker compose up -d
```

2. Зарегистрировать коннектор

```
curl -X POST -H "Content-Type: application/json" \
  --data @debezium/crm-connector.json \
  http://localhost:8083/connectors

```

3. Проверить, что коннектор активен

```
curl http://localhost:8083/connectors

```

В сервисе отётов данные теперь читаются из crm_clients и телеметрии (через Materialized View).

