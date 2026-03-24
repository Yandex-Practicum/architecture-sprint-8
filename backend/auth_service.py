"""
bionicpro-auth  —  BFF-сервис аутентификации.

Реализует:
  - Обмен authorization code (PKCE) на access/refresh токены через Keycloak
  - Хранение токенов на стороне сервера (in-memory session store)
  - Выдачу HttpOnly / Secure session cookie фронтенду
  - Ротацию session id при каждом запросе (session fixation prevention)
  - Автоматическое обновление access_token по refresh_token
"""

import json
import os
import secrets
import time
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="bionicpro-auth")

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "reports-frontend")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
SESSION_TTL = int(os.getenv("SESSION_TTL", "1800"))

TOKEN_ENDPOINT = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
LOGOUT_ENDPOINT = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/logout"
USERINFO_ENDPOINT = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/userinfo"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory session store: session_id -> { access_token, refresh_token, ... }
# ---------------------------------------------------------------------------
sessions: dict[str, dict] = {}


def _new_session_id() -> str:
    return secrets.token_urlsafe(32)


def _decode_token_payload(token: str) -> dict:
    """Extract payload from a JWT without signature verification (lab only)."""
    import base64
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def _is_token_expired(token: str) -> bool:
    payload = _decode_token_payload(token)
    exp = payload.get("exp", 0)
    return time.time() >= exp


async def _refresh_access_token(session: dict) -> bool:
    """Use refresh_token to get a new access_token from Keycloak."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_ENDPOINT,
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": session["refresh_token"],
            },
        )
    if resp.status_code != 200:
        return False
    data = resp.json()
    session["access_token"] = data["access_token"]
    session["refresh_token"] = data.get("refresh_token", session["refresh_token"])
    session["updated_at"] = time.time()
    return True


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key="SESSION_ID",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_TTL,
        path="/",
    )


async def get_current_session(request: Request) -> dict:
    """
    Dependency: extracts the current session from the cookie,
    validates it, auto-refreshes the access_token if expired,
    and performs session rotation.
    """
    session_id = request.cookies.get("SESSION_ID")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = sessions[session_id]

    if time.time() - session.get("created_at", 0) > SESSION_TTL:
        sessions.pop(session_id, None)
        raise HTTPException(status_code=401, detail="Session expired")

    if _is_token_expired(session["access_token"]):
        ok = await _refresh_access_token(session)
        if not ok:
            sessions.pop(session_id, None)
            raise HTTPException(status_code=401, detail="Token refresh failed")

    session["_old_session_id"] = session_id
    return session


def rotate_session(session: dict, response: Response) -> str:
    """Move tokens to a new session id (session fixation prevention)."""
    old_id = session.pop("_old_session_id", None)
    new_id = _new_session_id()
    sessions[new_id] = session
    if old_id and old_id in sessions:
        del sessions[old_id]
    _set_session_cookie(response, new_id)
    return new_id


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/callback")
async def auth_callback(request: Request, response: Response):
    """
    Frontend sends { code, code_verifier, redirect_uri } after Keycloak
    redirects back.  This endpoint exchanges the code for tokens.
    """
    body = await request.json()
    code = body.get("code")
    code_verifier = body.get("code_verifier")
    redirect_uri = body.get("redirect_uri")

    if not code or not code_verifier or not redirect_uri:
        raise HTTPException(status_code=400, detail="Missing code / code_verifier / redirect_uri")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_ENDPOINT,
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Token exchange failed")

    data = resp.json()
    session_id = _new_session_id()
    sessions[session_id] = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _set_session_cookie(response, session_id)
    payload = _decode_token_payload(data["access_token"])
    return {
        "username": payload.get("preferred_username"),
        "roles": payload.get("realm_access", {}).get("roles", []),
    }


@app.post("/logout")
async def auth_logout(request: Request, response: Response):
    session_id = request.cookies.get("SESSION_ID")
    if session_id and session_id in sessions:
        session = sessions.pop(session_id)
        async with httpx.AsyncClient() as client:
            await client.post(
                LOGOUT_ENDPOINT,
                data={
                    "client_id": CLIENT_ID,
                    "refresh_token": session.get("refresh_token", ""),
                },
            )
    response.delete_cookie("SESSION_ID", path="/")
    return {"status": "logged_out"}


@app.get("/session")
async def auth_session(
    response: Response,
    session: dict = Depends(get_current_session),
):
    new_id = rotate_session(session, response)
    payload = _decode_token_payload(session["access_token"])
    return {
        "username": payload.get("preferred_username"),
        "roles": payload.get("realm_access", {}).get("roles", []),
    }


@app.get("/userinfo")
async def auth_userinfo(
    response: Response,
    session: dict = Depends(get_current_session),
):
    """Proxy to Keycloak userinfo, using server-side access_token."""
    rotate_session(session, response)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {session['access_token']}"},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Userinfo request failed")
    return resp.json()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}
