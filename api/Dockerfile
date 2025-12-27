FROM python:3.11-slim

WORKDIR /app

COPY req.txt .
RUN pip install -r req.txt

COPY main.py .

CMD ["fastapi", "dev", "main.py", "--host", "0.0.0.0"]
