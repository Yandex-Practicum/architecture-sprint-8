# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from app.routers import reports

# Настройка логирования
logging.basicConfig(
    level=logging.INFO if os.getenv("DEBUG", "False").lower() != "true" else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Конфигурация
APP_NAME = os.getenv("APP_NAME", "BionicPRO Report Service")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(
    title=APP_NAME,
    description="Report Service for BionicPRO",
    version="1.0.0",
    debug=DEBUG
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(reports.router)

@app.get("/")
async def root():
    return {
        "service": APP_NAME,
        "status": "running",
        "environment": ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}