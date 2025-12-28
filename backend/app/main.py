"""
BionicPRO Backend API

Сервис для получения отчётов о работе бионических протезов.
Данные запрашиваются из ClickHouse (OLAP) без сложных вычислений в реальном времени.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import reports_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание приложения
app = FastAPI(
    title="BionicPRO Reports API",
    description="""
    API для получения отчётов о работе бионических протезов.
    
    ## Возможности
    
    * **Получение отчётов** - данные о работе протеза из OLAP-базы
    * **Фильтрация по датам** - выбор периода отчёта
    * **Статус данных** - информация о последней обработке ETL
    
    ## Источник данных
    
    Данные подготавливаются ETL-процессом Apache Airflow и хранятся в ClickHouse.
    Отчёты формируются ежедневно в 02:00.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(reports_router)


@app.get("/", tags=["health"])
async def root():
    """Корневой эндпоинт."""
    return {
        "service": "BionicPRO Reports API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Проверка здоровья сервиса."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

