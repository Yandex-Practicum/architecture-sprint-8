# ./airflow/Dockerfile
FROM apache/airflow:2.9.3

USER root

RUN mkdir -p /opt/airflow/logs/scheduler && \
    chown -R 50000:0 /opt/airflow/logs && \
    chmod -R 755 /opt/airflow/logs

COPY requirements.txt /tmp/requirements.txt

USER 50000
RUN pip install --no-cache-dir -r /tmp/requirements.txt