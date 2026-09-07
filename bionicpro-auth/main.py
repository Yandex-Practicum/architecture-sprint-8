import os
import uuid
import httpx
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Хранилище сессий в памяти
sessions = {}

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
CLIENT_ID = os.getenv("CLIENT_ID", "reports-frontend")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/auth/login")
async def login(body: LoginRequest, response: Response):
    token_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"

    async with httpx.AsyncClient() as client:
        resp = await client.post(token_url, data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": body.username,
            "password": body.password,
        })

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    tokens = resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "username": body.username
    }

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=3600
    )

    return {"status": "ok"}


@app.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]

    response.delete_cookie("session_id")
    return {"status": "ok"}


@app.get("/auth/me")
async def me(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = sessions[session_id]
    return {"username": session["username"]}


@app.get("/reports")
async def get_report(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = sessions[session_id]
    username = session["username"]

    return {
        "username": username,
        "url": f"http://localhost:8000/reports/download/{username}",
        "data": {
            "prosthesis_id": "PROS-001",
            "usage_hours": 120,
            "battery_cycles": 45,
            "movements_count": 15000
        }
    }


@app.get("/health")
async def health():
    return {"status": "ok"}