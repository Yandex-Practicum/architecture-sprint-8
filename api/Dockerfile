# Use official Python image
FROM python:3.10

# Set working directory
WORKDIR /app

# Copy dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py ./


# Expose the port FastAPI runs on
EXPOSE 8000

# Run the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
