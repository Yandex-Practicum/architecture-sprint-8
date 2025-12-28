FROM apache/airflow:2.7.3-python3.11

USER root

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Копирование requirements
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Копирование DAGs
COPY dags/ /opt/airflow/dags/

