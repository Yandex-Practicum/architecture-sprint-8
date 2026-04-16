FROM continuumio/miniconda3:latest

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Установка Airflow через conda
RUN conda install -c conda-forge apache-airflow=2.8.1 python=3.9 -y

# Установка pandas и других пакетов через conda
RUN conda install -c conda-forge \
    pandas=2.0.3 \
    numpy=1.24.3 \
    psycopg2 \
    apache-airflow-providers-postgres==5.5.2 \
    clickhouse-driver \
    -y

COPY dags/ /opt/airflow/dags/

ENV AIRFLOW_HOME=/opt/airflow
ENV AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres_airflow/airflow

CMD ["airflow", "webserver"]