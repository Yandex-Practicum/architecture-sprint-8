from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import reports

app = FastAPI(
    title="BionicPRO Reports API",
    description="API для получения отчётов о работе бионических протезов",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reports.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}