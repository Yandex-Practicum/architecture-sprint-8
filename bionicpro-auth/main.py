from fastapi import FastAPI
import uvicorn
from app.routes import auth
from app.config import settings
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
import secrets

app = FastAPI(title="BionicPRO Auth Service")

# Добавляем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(32))

app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
