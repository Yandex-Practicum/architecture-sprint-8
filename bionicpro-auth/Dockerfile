FROM python:3.13-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Открытие порта
EXPOSE 5050

# Запуск приложения
CMD ["python", "app.py"]
