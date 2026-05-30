FROM apache/airflow:2.9.1-python3.9

USER root

# Установка системных зависимостей (только необходимые для клиента)
RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean

USER airflow

# Установка Python зависимостей
COPY requirements.txt /requirements.txt
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r /requirements.txt