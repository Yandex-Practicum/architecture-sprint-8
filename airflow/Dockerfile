FROM apache/airflow:2.7.0

USER root

# Установка дополнительных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Копирование requirements
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Создание директорий для логов и плагинов
RUN mkdir -p /opt/airflow/logs /opt/airflow/plugins

# Копирование DAG файлов
COPY dags/ /opt/airflow/dags/
