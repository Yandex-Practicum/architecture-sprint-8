FROM apache/airflow:2.8.1-python3.11

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

USER airflow
RUN pip install --no-cache-dir \
    "psycopg2-binary==2.9.9"
