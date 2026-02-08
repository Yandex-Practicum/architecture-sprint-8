FROM apache/airflow:2.9.1-python3.9
USER root

COPY requirements.txt /tmp/requirements.txt

USER airflow

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

USER root
RUN rm -f /tmp/requirements.txt
USER airflow

WORKDIR /opt/airflow