# ============================================================================
# Apache Airflow Dockerfile for BionicPRO ETL
# ============================================================================
FROM apache/airflow:2.8.1-python3.11

USER root

# CLI Airflow теперь находится в переменной PATH для entrypoint health check
ENV PATH="/home/airflow/.local/bin:${PATH}"

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Копируем requirements
COPY requirements.txt /tmp/requirements.txt

# Установка Python зависимостей
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Копируем DAGs
COPY dags/ /opt/airflow/dags/

# Копируем плагины (если есть)
COPY plugins/ /opt/airflow/plugins/
