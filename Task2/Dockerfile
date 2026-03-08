FROM apache/airflow:2.9.1-python3.9
USER root

# Install Python dependencies
COPY requirements.txt /requirements.txt
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r /requirements.txt