FROM apache/airflow:2.11.0-python3.11

USER root

COPY requirements.txt /requirements.txt
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r /requirements.txt

USER airflow