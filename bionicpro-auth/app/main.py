import os
import uuid
import secrets
import hashlib
import base64
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Response, Query, Cookie, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

try:
    import redis
except Exception:
    redis = None

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
CLIENT_ID = os.getenv("CLIENT_ID", "reports-frontend")
CALLBACK_URL = os.getenv("CALLBACK_URL", "http://bionicpro-auth:8000/auth/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
REDIS_URL = os.getenv("REDIS_URL")
COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "bionicpro_session")
SESSION_TTL = int(os.getenv("SESSION_TTL", "3600"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

app = FastAPI(title="bionicpro-auth (skeleton)")

# simple stores
pkce_store = {}  # state -> code_verifier
inmem_sessions = {}  # session_id -> data


class SessionStore:
    def __init__(self, redis_url: Optional[str]):
        self.redis = None
        if redis_url and redis:
            self.redis = redis.from_url(redis_url)

    def set(self, session_id: str, data: dict, ttl: Optional[int] = None):
        if self.redis:
            self.redis.hmset(session_id, data)
            if ttl:
                self.redis.expire(session_id, ttl)
        else:
            inmem_sessions[session_id] = data

    def get(self, session_id: str) -> Optional[dict]:
        if self.redis:
            data = self.redis.hgetall(session_id)
            if not data:
                return None
            # decode bytes
            return {k.decode(): v.decode() for k, v in data.items()}
        return inmem_sessions.get(session_id)

    def delete(self, session_id: str):
        if self.redis:
            self.redis.delete(session_id)
        else:
            inmem_sessions.pop(session_id, None)


session_store = SessionStore(REDIS_URL)


def make_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


@app.get("/auth/login")
def login(redirect: Optional[str] = Query(None)):
    state = secrets.token_urlsafe(16)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = make_code_challenge(code_verifier)
    pkce_store[state] = code_verifier
    redirect_uri = CALLBACK_URL
    auth_url = (
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/auth"
        f"?client_id={CLIENT_ID}&response_type=code&scope=openid&redirect_uri={redirect_uri}"
        f"&code_challenge={code_challenge}&code_challenge_method=S256&state={state}"
    )
    return RedirectResponse(auth_url)


@app.get("/auth/callback")
async def callback(request: Request, code: str = Query(...), state: str = Query(...), r: Optional[str] = Query(None)):
    verifier = pkce_store.pop(state, None)
    if not verifier:
        raise HTTPException(status_code=400, detail="invalid state or pkce verifier not found")

    token_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    async with httpx.AsyncClient() as client:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "redirect_uri": CALLBACK_URL,
            "code_verifier": verifier,
        }
        resp = await client.post(token_url, data=data)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="token exchange failed")
        tokens = resp.json()

    session_id = str(uuid.uuid4())
    # store tokens as-is (demo); encrypt in production
    session_store.set(session_id, {"access_token": tokens.get("access_token", ""), "refresh_token": tokens.get("refresh_token", ""), "id_token": tokens.get("id_token", "")}, ttl=SESSION_TTL)
    target = r or FRONTEND_URL
    response = RedirectResponse(target)
    response.set_cookie(key=COOKIE_NAME, value=session_id, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=SESSION_TTL)
    return response


@app.post("/auth/refresh")
async def refresh(session_id: Optional[str] = Cookie(None)):
    if not session_id:
        raise HTTPException(status_code=401, detail="no session")
    sess = session_store.get(session_id)
    if not sess:
        raise HTTPException(status_code=401, detail="session not found")
    refresh_token = sess.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="no refresh token")

    token_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    async with httpx.AsyncClient() as client:
        data = {"grant_type": "refresh_token", "client_id": CLIENT_ID, "refresh_token": refresh_token}
        resp = await client.post(token_url, data=data)
        if resp.status_code != 200:
            session_store.delete(session_id)
            raise HTTPException(status_code=502, detail="refresh failed")
        tokens = resp.json()
    session_store.set(session_id, {"access_token": tokens.get("access_token", ""), "refresh_token": tokens.get("refresh_token", ""), "id_token": tokens.get("id_token", "")}, ttl=SESSION_TTL)
    return JSONResponse({"status": "ok"})


@app.post("/auth/logout")
async def logout(session_id: Optional[str] = Cookie(None)):
    if not session_id:
        return JSONResponse({"status": "no session"})
    sess = session_store.get(session_id)
    if sess:
        # optional: call Keycloak end session / revoke
        session_store.delete(session_id)
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/session/validate")
async def session_validate(session_id: Optional[str] = Cookie(None)):
    if not session_id:
        raise HTTPException(status_code=401, detail="no session cookie")
    sess = session_store.get(session_id)
    if not sess:
        raise HTTPException(status_code=401, detail="invalid session")
    access_token = sess.get("access_token")
    # attempt to fetch userinfo
    userinfo_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/userinfo"
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = await client.get(userinfo_url, headers=headers)
        if resp.status_code == 200:
            return resp.json()
    # if userinfo failed, tell caller to refresh
    return JSONResponse({"status": "needs_refresh"}, status_code=401)
