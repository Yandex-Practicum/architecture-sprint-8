# Задание 2. Разработка сервиса отчётов

## Задача 1. Создать архитектуру решения для подготовки и получения отчётов

[Архитектура решения](https://github.com/tammaco/architecture-pro-bionicpro/Task2/BionicPRO_C4_model.drawio.xml)

## Задача 2. Разработать Airflow DAG и настроить его на запуск по расписанию

1. Добавлены тестовые данные по [пользователям] (https://github.com/tammaco/architecture-pro-bionicpro/airflow/data/crm_users.csv) и [телеметрии] (https://github.com/tammaco/architecture-pro-bionicpro/airflow/data/sensor_data.csv).

2. Создан [DAG-файл](https://github.com/tammaco/architecture-pro-bionicpro/airflow/dags/user_report.py) для агрегации данных, запуск в 2 часа ночи:

```
schedule_interval='0 2 * * *'
```

3. Обновлён docker-compose.yml

```
postgres_airflow:
    image: postgres:14-alpine
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - ./airflow/postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "airflow"]
      interval: 10s
      retries: 5
      start_period: 5s
    networks:
      - bionic-network
    restart: unless-stopped

  airflow-init:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      postgres_airflow:
        condition: service_healthy
    environment:
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres_airflow/airflow
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/requirements.txt:/opt/airflow/requirements.txt
    command: >
      bash -c "
      pip install -r /opt/airflow/requirements.txt &&
      airflow db init &&
      airflow users create --username admin --password admin --firstname admin --lastname admin --role Admin --email admin@example.com
      "
    networks:
      - bionic-network

  airflow-webserver:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      postgres_airflow:
        condition: service_healthy
      airflow-init:
        condition: service_completed_successfully
    environment:
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres_airflow/airflow
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
    ports:
      - "8085:8080"
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/data:/opt/airflow/data
    command: webserver
    networks:
      - bionic-network
    restart: unless-stopped

  airflow-scheduler:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      postgres_airflow:
        condition: service_healthy
      airflow-init:
        condition: service_completed_successfully
    environment:
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres_airflow/airflow
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/data:/opt/airflow/data
    command: scheduler
    networks:
      - bionic-network
    restart: unless-stopped
```

4. После поднятия контейнеров, в админке можно запустить user_report и проверить.
[Результат](https://github.com/tammaco/architecture-pro-bionicpro/Task2/screenshots/user_report.png), создан [отчёт](https://github.com/tammaco/architecture-pro-bionicpro/airflow/data/user_report_mart.csv): 

## Задача 3. Создайте бэкенд-часть приложения для API

Добавлена БД clickhouse с [инициализацией](https://github.com/tammaco/architecture-pro-bionicpro/db/init-clickhouse-db.sql) базы данных и созданием талицы отчёта.

После поднятия контенера, нужно добавить пользователя внутри него:

```
docker exec -it clickhouse clickhouse-client

CREATE USER IF NOT EXISTS report IDENTIFIED WITH plaintext_password BY 'report';

GRANT ALL ON bionicpro.* TO report;

```

Реализован сервис отчётов на C# - microservices/report-service, который возвращает отчёт по пользователю.

## Задача 4. Реализуйте ограничение доступа к эндпоинту отчётности

Добавлена проверка пользователя в ReportController.

## Задача 5. Добавьте в UI кнопку получения отчёта и вызова эндпоинта его генерации

Добавлена кнопка получения отчёта

