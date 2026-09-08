import os
import uuid
import httpx
import clickhouse_connect
from fastapi import FastAPI, HTTPException, Request, Response
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

sessions = {}

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
CLIENT_ID = os.getenv("CLIENT_ID", "reports-frontend")
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")


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
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
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
    return {"username": sessions[session_id]["username"]}


@app.get("/reports")
async def get_report(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = sessions[session_id]["username"]

    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=8123,
            database='bionicpro'
        )

        result = client.query(
            "SELECT username, full_name, prosthesis_id, total_usage_hours, total_battery_cycles, total_movements, last_recorded_at FROM prosthesis_report WHERE username = {username:String} LIMIT 1",
            parameters={"username": username}
        )

        if not result.result_rows:
            raise HTTPException(status_code=404, detail="No report found for this user")

        row = result.result_rows[0]
        return {
            "username": row[0],
            "full_name": row[1],
            "prosthesis_id": row[2],
            "data": {
                "prosthesis_id": row[2],
                "usage_hours": row[3],
                "battery_cycles": row[4],
                "movements_count": row[5],
                "last_recorded_at": str(row[6])
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}