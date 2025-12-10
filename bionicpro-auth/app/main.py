import base64
import hashlib
import os
import secrets
import time
from typing import Dict, Optional, Tuple

import httpx
from cryptography.fernet import Fernet
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.cors import CORSMiddleware
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bionicpro-auth")


KEYCLOAK_INTERNAL_URL = os.getenv("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080")
KEYCLOAK_PUBLIC_URL = os.getenv("KEYCLOAK_PUBLIC_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "reports-frontend")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
REPORTS_API_URL = os.getenv("REPORTS_API_URL", "http://reports-api:9000")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "900"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

TOKEN_ENDPOINT = f"{KEYCLOAK_INTERNAL_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
AUTH_ENDPOINT = f"{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"

_fernet_key = os.getenv("AUTH_ENC_KEY")
if not _fernet_key:
    # generate ephemeral key for dev
    _fernet_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
fernet = Fernet(_fernet_key)

pending_auth: Dict[str, Tuple[str, float]] = {}
sessions: Dict[str, Dict[str, object]] = {}

app = FastAPI(title="bionicpro-auth", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _pkce_pair() -> Tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _set_session_cookie(resp: Response, session_id: str):
    resp.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )


def _encrypt(token: str) -> str:
    return fernet.encrypt(token.encode()).decode()


def _decrypt(token_enc: str) -> str:
    return fernet.decrypt(token_enc.encode()).decode()


def _decode_sub(access_token: str) -> Optional[str]:
    # быстрая декодировка payload JWT без валидации подписи
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        import json
        sub = json.loads(base64.urlsafe_b64decode(payload_b64).decode()).get("sub")
        return sub
    except Exception:
        return None


def _subject_to_uid(sub: str) -> int:
    """
    Приводим subject из токена (обычно UUID/строка) к детерминированному UInt64,
    чтобы согласовать с ClickHouse схемой reports_mart (user_id UInt64).
    """
    try:
        return int(sub)
    except (ValueError, TypeError):
        import hashlib

        return int.from_bytes(hashlib.sha256(sub.encode()).digest()[:8], "big")


async def _exchange_code(code: str, code_verifier: str, redirect_uri: str) -> Dict[str, object]:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30.0,
        trust_env=False,
    ) as client:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": KEYCLOAK_CLIENT_ID,
            "code_verifier": code_verifier,
        }
        try:
            resp = await client.post(TOKEN_ENDPOINT, data=data)
        except httpx.RequestError as exc:
            import traceback
            logger.error(
                "token exchange request error exc=%r cause=%r type=%s",
                exc,
                exc.__cause__,
                type(exc),
                exc_info=True,
            )
            traceback.print_exc()
            raise HTTPException(
                status_code=502,
                detail=f"Token exchange failed: {exc!r} cause={exc.__cause__!r} url={TOKEN_ENDPOINT}",
            ) from exc
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail=f"Failed to exchange code: {resp.status_code} {resp.text}")
        return resp.json()


async def _refresh_tokens(refresh_token: str) -> Dict[str, object]:
    async with httpx.AsyncClient() as client:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": KEYCLOAK_CLIENT_ID,
        }
        resp = await client.post(TOKEN_ENDPOINT, data=data)
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Failed to refresh token")
        return resp.json()


def _store_session(access_token: str, refresh_token: str, access_expires_in: int, refresh_expires_in: Optional[int]) -> str:
    now = time.time()
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "access_token": access_token,
        "access_expires_at": now + max(access_expires_in - 10, 30),
        "refresh_token_enc": _encrypt(refresh_token),
        "refresh_expires_at": now + (refresh_expires_in - 30 if refresh_expires_in else SESSION_TTL_SECONDS),
        "created_at": now,
    }
    return session_id


def _get_session(session_id: str) -> Dict[str, object]:
    data = sessions.get(session_id)
    if not data:
        raise HTTPException(status_code=401, detail="Session not found")
    now = time.time()
    if data["refresh_expires_at"] < now:
        sessions.pop(session_id, None)
        raise HTTPException(status_code=401, detail="Session expired")
    return data


async def _ensure_fresh_tokens(session_id: str) -> Tuple[str, Dict[str, object]]:
    data = _get_session(session_id)
    now = time.time()
    access_token = data["access_token"]
    if data["access_expires_at"] <= now:
        refreshed = await _refresh_tokens(_decrypt(data["refresh_token_enc"]))
        access_token = refreshed["access_token"]
        data["access_token"] = access_token
        data["access_expires_at"] = now + max(refreshed.get("expires_in", 120) - 10, 30)
        if "refresh_token" in refreshed:
            data["refresh_token_enc"] = _encrypt(refreshed["refresh_token"])
            data["refresh_expires_at"] = now + (refreshed.get("refresh_expires_in", SESSION_TTL_SECONDS) - 30)
    return access_token, data


def _rotate_session(old_id: str, data: Dict[str, object]) -> str:
    new_id = secrets.token_urlsafe(32)
    sessions[new_id] = data
    sessions.pop(old_id, None)
    return new_id


@app.get("/auth/login")
async def login():
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    pending_auth[state] = (verifier, time.time())
    redirect_uri = f"{BACKEND_URL}/auth/callback"
    url = (
        f"{AUTH_ENDPOINT}?response_type=code&client_id={KEYCLOAK_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=openid%20profile%20email"
        f"&code_challenge={challenge}&code_challenge_method=S256"
        f"&state={state}"
    )
    return RedirectResponse(url=url, status_code=302)


@app.get("/auth/callback")
async def auth_callback(code: str, state: str, response: Response):
    entry = pending_auth.pop(state, None)
    if not entry:
        raise HTTPException(status_code=400, detail="Invalid state")
    code_verifier, created_at = entry
    if time.time() - created_at > 300:
        raise HTTPException(status_code=400, detail="Authorization request expired")

    redirect_uri = f"{BACKEND_URL}/auth/callback"
    token_data = await _exchange_code(code, code_verifier, redirect_uri)
    session_id = _store_session(
        token_data["access_token"],
        token_data["refresh_token"],
        token_data.get("expires_in", 120),
        token_data.get("refresh_expires_in"),
    )
    resp = RedirectResponse(url=FRONTEND_URL, status_code=302)
    _set_session_cookie(resp, session_id)
    return resp


async def require_session(session_id: Optional[str] = Cookie(default=None)):
    if not session_id:
        raise HTTPException(status_code=401, detail="No session cookie")
    access_token, data = await _ensure_fresh_tokens(session_id)
    sub = _decode_sub(access_token)
    if not sub:
        raise HTTPException(status_code=401, detail="User not authenticated")
    user_id = _subject_to_uid(sub)
    new_session_id = _rotate_session(session_id, data)
    return access_token, new_session_id, user_id


@app.get("/auth/session")
async def session_info(response: Response, payload=Depends(require_session)):
    _, new_session_id, _ = payload
    resp = JSONResponse({"status": "ok"})
    _set_session_cookie(resp, new_session_id)
    return resp


@app.post("/auth/logout")
async def logout(response: Response, session_id: Optional[str] = Cookie(default=None)):
    if session_id:
        sessions.pop(session_id, None)
    resp = JSONResponse({"status": "logged_out"})
    resp.delete_cookie("session_id")
    return resp


@app.get("/reports")
async def reports_proxy(response: Response, payload=Depends(require_session)):
    access_token, new_session_id, user_id = payload
    _set_session_cookie(response, new_session_id)

    # Проксируем запрос в reports-api, пробрасывая user_id
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info("proxy /reports with user_id=%s", user_id)
            r = await client.get(
                f"{REPORTS_API_URL}/reports",
                headers={"X-User-Id": str(user_id)},
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"reports-api unreachable: {exc}")

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return r.json()

