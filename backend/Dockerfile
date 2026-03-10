# backend/Dockerfile
# 1️⃣ Используем официальный Python 3.11
FROM python:3.11-slim

# 2️⃣ Рабочая директория внутри контейнера
WORKDIR /app

# 3️⃣ Копируем зависимости
COPY requirements.txt .

# 4️⃣ Устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 5️⃣ Копируем весь код приложения
COPY . .

# 6️⃣ Команда по умолчанию для запуска
# Используем Uvicorn для FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]