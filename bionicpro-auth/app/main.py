import os
import secrets
import time
from typing import Optional

import httpx
import redis
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse

app = FastAPI(title="bionicpro-auth")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

KEYCLOAK_BASE_URL = "http://keycloak:8080"
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")

OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "bionicpro-auth")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")

COOKIE_NAME = os.getenv("COOKIE_NAME", "bpsid")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
AUTH_PUBLIC_URL = os.getenv("AUTH_PUBLIC_URL", "http://localhost:8001").rstrip("/")

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


@app.get("/health")
def health():
    return {"status": "ok"}


def _kc_authorize_url(state: str) -> str:
    redirect_uri = f"{AUTH_PUBLIC_URL}/auth/callback"
    return (
        f"http://localhost:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
        f"?client_id={OIDC_CLIENT_ID}"
        f"&response_type=code"
        f"&scope=openid"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )



@app.get("/auth/login")
def auth_login():
    state = secrets.token_urlsafe(32)
    r.setex(f"oidc:state:{state}", 300, "1")  # 5 минут
    return RedirectResponse(_kc_authorize_url(state))


@app.get("/auth/callback")
async def auth_callback(code: Optional[str] = None, state: Optional[str] = None):
    if not code or not state:
        return JSONResponse({"error": "missing code/state"}, status_code=400)

    key_state = f"oidc:state:{state}"
    if not r.get(key_state):
        return JSONResponse({"error": "invalid state"}, status_code=400)
    r.delete(key_state)

    if not OIDC_CLIENT_SECRET:
        return JSONResponse({"error": "OIDC_CLIENT_SECRET is not set"}, status_code=500)

    token_url = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    redirect_uri = f"{AUTH_PUBLIC_URL}/auth/callback"

    data = {
        "grant_type": "authorization_code",
        "client_id": OIDC_CLIENT_ID,
        "client_secret": OIDC_CLIENT_SECRET,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(token_url, data=data)

    if resp.status_code != 200:
        return JSONResponse(
            {"error": "token exchange failed", "status": resp.status_code, "body": resp.text},
            status_code=502,
        )

    tokens = resp.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = int(tokens.get("expires_in", 0))

    if not access_token or not refresh_token:
        return JSONResponse({"error": "missing tokens in response"}, status_code=502)

    session_id = secrets.token_urlsafe(32)
    now = int(time.time())

    r.hset(
        f"sess:{session_id}",
        mapping={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access_exp": str(now + max(expires_in, 0)),
        },
    )
    r.expire(f"sess:{session_id}", SESSION_TTL_SECONDS)

    response = RedirectResponse(f"{FRONTEND_URL}/", status_code=302)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
    return response


async def _refresh_access_token(session_id: str):
    data = r.hgetall(f"sess:{session_id}")
    if not data or not data.get("refresh_token"):
        return False

    token_url = f"http://keycloak:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": OIDC_CLIENT_ID,
        "client_secret": OIDC_CLIENT_SECRET,
        "refresh_token": data["refresh_token"],
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(token_url, data=payload)

    if resp.status_code != 200:
        return False

    tokens = resp.json()
    now = int(time.time())
    r.hset(
        f"sess:{session_id}",
        mapping={
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", data["refresh_token"]),
            "access_exp": str(now + int(tokens.get("expires_in", 0))),
        },
    )
    return True




@app.get("/session/me")
async def session_me(request: Request):
    sid = request.cookies.get(COOKIE_NAME)
    if not sid:
        return JSONResponse({"authenticated": False}, status_code=401)

    data = r.hgetall(f"sess:{sid}")
    if not data:
        return JSONResponse({"authenticated": False}, status_code=401)

    now = int(time.time())
    access_exp = int(data.get("access_exp", "0"))

    if access_exp <= now:
        ok = await _refresh_access_token(sid)
        if not ok:
            return JSONResponse({"authenticated": False}, status_code=401)

        data = r.hgetall(f"sess:{sid}")

    # --- session rotation ---
    new_sid = secrets.token_urlsafe(32)

    r.rename(f"sess:{sid}", f"sess:{new_sid}")
    r.expire(f"sess:{new_sid}", SESSION_TTL_SECONDS)

    response = JSONResponse({
        "authenticated": True,
        "session": {
            "id": new_sid,
            "access_exp": r.hget(f"sess:{new_sid}", "access_exp"),
        },
    })

    response.set_cookie(
        key=COOKIE_NAME,
        value=new_sid,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )
    return response


@app.post("/auth/logout")
def auth_logout(request: Request):
    sid = request.cookies.get(COOKIE_NAME)
    if sid:
        r.delete(f"sess:{sid}")
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp
