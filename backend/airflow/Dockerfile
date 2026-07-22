FROM  apache/airflow:2.11.2-python3.10
USER root

# Install Python dependencies
COPY ./airflow-requirements.txt /requirements.txt
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r /requirements.txt