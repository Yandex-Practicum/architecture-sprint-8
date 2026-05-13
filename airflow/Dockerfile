FROM apache/airflow:2.7.0

USER root
RUN apt-get update && apt-get install -y gcc python3-dev

USER airflow
COPY requirements.txt /opt/airflow/
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt