from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.router import router

app = FastAPI(title="BionicPRO Report API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(router)
