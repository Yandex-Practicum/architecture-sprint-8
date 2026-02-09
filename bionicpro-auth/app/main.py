import os
import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx
import redis
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

KEYCLOAK_BASE = os.environ["KEYCLOAK_BASE"]              # https://kc.example.com
REALM = os.environ["KEYCLOAK_REALM"]                      # bionicpro
CLIENT_ID = os.environ["KEYCLOAK_CLIENT_ID"]              # bionicpro-auth
CLIENT_SECRET = os.environ["KEYCLOAK_CLIENT_SECRET"]      # ***
REDIRECT_URI = os.environ["KEYCLOAK_REDIRECT_URI"]        # https://auth.example.com/auth/callback

COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "bp_session")
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN")           # optional
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=False)

FERNET_KEY = os.environ["FERNET_KEY"]  # base64 urlsafe 32 bytes
fernet = Fernet(FERNET_KEY)

app = FastAPI()

AUTH_ENDPOINT = f"{KEYCLOAK_BASE}/realms/{REALM}/protocol/openid-connect/auth"
TOKEN_ENDPOINT = f"{KEYCLOAK_BASE}/realms/{REALM}/protocol/openid-connect/token"

FRONTEND_RETURN_URL = os.environ.get("FRONTEND_RETURN_URL", "http://localhost:3000/")
FRONTEND_ORIGINS = [
    "http://localhost:3000",        # dev
    "https://frontend.bionicpro.com"  # prod (пример)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Accept"
    ],
)


# --------- helpers ---------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def build_pkce_pair():
    code_verifier = _b64url(secrets.token_bytes(32))
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = _b64url(digest)
    return code_verifier, code_challenge

def set_session_cookie(resp: Response, session_id: str):
    resp.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
        domain=COOKIE_DOMAIN,
        max_age=60 * 60 * 24,  # 1 day (можно меньше/больше)
    )

def clear_session_cookie(resp: Response):
    resp.delete_cookie(key=COOKIE_NAME, path="/", domain=COOKIE_DOMAIN)

def redis_key(prefix: str, session_id: str) -> str:
    return f"bp:{prefix}:{session_id}"

def store_tokens(session_id: str, access_token: str, access_expires_in: int, refresh_token: str, refresh_ttl_sec: int):
    # access: plain, TTL = expires_in
    r.setex(redis_key("at", session_id), access_expires_in, access_token.encode("utf-8"))

    # refresh: encrypted, TTL > access
    enc_rt = fernet.encrypt(refresh_token.encode("utf-8"))
    r.setex(redis_key("rt", session_id), refresh_ttl_sec, enc_rt)

def load_access(session_id: str) -> str | None:
    v = r.get(redis_key("at", session_id))
    return v.decode("utf-8") if v else None

def load_refresh(session_id: str) -> str | None:
    v = r.get(redis_key("rt", session_id))
    if not v:
        return None
    try:
        return fernet.decrypt(v).decode("utf-8")
    except Exception:
        return None

def delete_session(session_id: str):
    r.delete(redis_key("at", session_id), redis_key("rt", session_id))

def rotate_session(old_session_id: str) -> str:
    """
    Session fixation mitigation:
    - create new session id
    - move tokens to new keys
    - delete old keys
    """
    new_session_id = secrets.token_urlsafe(32)

    at = r.get(redis_key("at", old_session_id))
    rt = r.get(redis_key("rt", old_session_id))
    if not at or not rt:
        raise HTTPException(401, "Session not found")

    # Keep remaining TTLs
    at_ttl = r.ttl(redis_key("at", old_session_id))
    rt_ttl = r.ttl(redis_key("rt", old_session_id))

    pipe = r.pipeline()
    pipe.setex(redis_key("at", new_session_id), max(at_ttl, 1), at)
    pipe.setex(redis_key("rt", new_session_id), max(rt_ttl, 1), rt)
    pipe.delete(redis_key("at", old_session_id), redis_key("rt", old_session_id))
    pipe.execute()

    return new_session_id


# --------- auth flow ---------

@app.get("/auth/login")
def auth_login():
    state = secrets.token_urlsafe(24)
    code_verifier, code_challenge = build_pkce_pair()

    # state -> code_verifier mapping (short TTL)
    r.setex(f"bp:state:{state}".encode("utf-8"), 300, code_verifier.encode("utf-8"))

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(f"{AUTH_ENDPOINT}?{urlencode(params)}")


@app.get("/auth/callback")
async def auth_callback(code: str, state: str):
    # load and delete verifier (one-time)
    state_key = f"bp:state:{state}".encode("utf-8")
    verifier_raw = r.get(state_key)
    r.delete(state_key)
    if not verifier_raw:
        raise HTTPException(400, "Invalid state")

    code_verifier = verifier_raw.decode("utf-8")

    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(TOKEN_ENDPOINT, data=data)
    if token_resp.status_code != 200:
        raise HTTPException(401, f"Token exchange failed: {token_resp.text}")

    payload = token_resp.json()
    access_token = payload["access_token"]
    refresh_token = payload.get("refresh_token")
    expires_in = int(payload.get("expires_in", 120))

    if not refresh_token:
        raise HTTPException(500, "No refresh_token from Keycloak. Check realm/client settings.")

    # session must outlive access_token
    session_id = secrets.token_urlsafe(32)
    refresh_ttl = 60 * 60 * 24  # 24h (пример; можно подстроить под SSO session)

    store_tokens(session_id, access_token, expires_in, refresh_token, refresh_ttl)

    resp = RedirectResponse(url=FRONTEND_RETURN_URL, status_code=302)  # на фронт
    set_session_cookie(resp, session_id)
    return resp


@app.post("/auth/logout")
def auth_logout(request: Request):
    sid = request.cookies.get(COOKIE_NAME)
    resp = JSONResponse({"ok": True})
    if sid:
        delete_session(sid)
    clear_session_cookie(resp)
    return resp


# --------- token refresh + protected example ---------

async def ensure_access_token(session_id: str) -> str:
    at = load_access(session_id)
    if at:
        return at

    # access expired -> use refresh
    rt = load_refresh(session_id)
    if not rt:
        raise HTTPException(401, "Session expired")

    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": rt,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(TOKEN_ENDPOINT, data=data)

    if token_resp.status_code != 200:
        # refresh invalid -> force relogin
        delete_session(session_id)
        raise HTTPException(401, "Refresh failed")

    payload = token_resp.json()
    new_at = payload["access_token"]
    new_rt = payload.get("refresh_token", rt)  # при rotate refresh_token будет новый
    expires_in = int(payload.get("expires_in", 120))

    # refresh TTL оставим прежним (можно обновлять/скользить)
    rt_ttl = max(r.ttl(redis_key("rt", session_id)), 60)
    store_tokens(session_id, new_at, expires_in, new_rt, rt_ttl)
    return new_at


@app.get("/api/protected/ping")
async def protected_ping(request: Request):
    sid = request.cookies.get(COOKIE_NAME)
    if not sid:
        raise HTTPException(401, "No session")

    # ensure access (auto refresh)
    _ = await ensure_access_token(sid)

    # session rotation on every successful protected request
    new_sid = rotate_session(sid)

    resp = JSONResponse({"ok": True})
    set_session_cookie(resp, new_sid)
    return resp