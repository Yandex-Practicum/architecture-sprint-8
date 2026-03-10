from fastapi import FastAPI
from api.report_controller import router as report_router
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(
    title="BionicPRO Reports API",
    description="Reports service for prosthesis telemetry",
    version="1.1.0",
)

app.include_router(report_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # адрес твоего фронтенда
    allow_credentials=True,
    allow_methods=["*"],  # разрешаем все методы: GET, POST, OPTIONS...
    allow_headers=["*"],  # разрешаем все заголовки, включая Authorization
)

# ---------- Routers ----------
app.include_router(report_router)
@app.get("/health")
def health():
    return {"status": "ok"}