FROM apache/airflow:2.7.0

USER root

# Копируем requirements.txt
COPY requirements.txt /requirements.txt

# Переключаемся на пользователя airflow для установки пакетов
USER airflow

# Устанавливаем зависимости от имени пользователя airflow
RUN pip install --no-cache-dir -r /requirements.txt

