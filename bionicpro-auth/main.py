import hashlib
import base64
import secrets
import time

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

from config import settings
import session as session_mgr

app = FastAPI(title="BionicPRO Auth BFF")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _get_session_id(request: Request) -> str | None:
    return request.cookies.get(settings.SESSION_COOKIE_NAME)


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=False,  # Set True in production (HTTPS)
        samesite="lax",
        max_age=settings.SESSION_MAX_AGE,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
    )


async def _exchange_code(code: str, code_verifier: str) -> dict:
    """Exchange authorization code for tokens at Keycloak token endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.CLIENT_ID,
                "client_secret": settings.CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.REDIRECT_URI,
                "code_verifier": code_verifier,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Token exchange failed")
    return resp.json()


async def _refresh_access_token(refresh_token: str) -> dict:
    """Use refresh_token to obtain a new access_token from Keycloak."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.CLIENT_ID,
                "client_secret": settings.CLIENT_SECRET,
                "refresh_token": refresh_token,
            },
        )
    if resp.status_code != 200:
        return {}
    return resp.json()


async def _ensure_valid_token(session_data: dict, session_id: str) -> str | None:
    """
    Return a valid access_token. If expired, use refresh_token to get a new one.
    Updates session in Redis if refreshed. Returns None if refresh fails.
    """
    access_token = session_data["access_token"]
    expires_at = session_data.get("expires_at", 0)

    if time.time() < expires_at:
        return access_token

    # Access token expired — refresh it
    tokens = await _refresh_access_token(session_data["refresh_token"])
    if not tokens:
        return None

    session_data["access_token"] = tokens["access_token"]
    session_data["refresh_token"] = tokens.get("refresh_token", session_data["refresh_token"])
    session_data["expires_at"] = time.time() + tokens.get("expires_in", 120)
    if "id_token" in tokens:
        session_data["id_token"] = tokens["id_token"]

    session_mgr.update_session(session_id, session_data)
    return tokens["access_token"]


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.get("/auth/login")
async def login():
    """Initiate OAuth2 Authorization Code + PKCE flow."""
    code_verifier, code_challenge = _generate_pkce_pair()
    state = secrets.token_urlsafe(32)

    # Store code_verifier in Redis keyed by state
    session_mgr.store_pkce_verifier(state, code_verifier)

    params = {
        "response_type": "code",
        "client_id": settings.CLIENT_ID,
        "redirect_uri": settings.REDIRECT_URI,
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{settings.authorization_url}?{query}")


@app.get("/auth/callback")
async def callback(code: str, state: str):
    """Handle Keycloak redirect after user authentication."""
    # Retrieve PKCE verifier
    code_verifier = session_mgr.get_pkce_verifier(state)
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    # Exchange code for tokens
    tokens = await _exchange_code(code, code_verifier)

    # Create server-side session
    session_id = session_mgr.create_session(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=tokens.get("expires_in", 120),
        id_token=tokens.get("id_token"),
    )

    # Redirect to frontend with HTTP-only session cookie
    response = RedirectResponse(url=settings.FRONTEND_URL, status_code=302)
    _set_session_cookie(response, session_id)
    return response


@app.get("/auth/me")
async def me(request: Request):
    """Return authenticated user info."""
    session_id = _get_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = session_mgr.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=401, detail="Session expired")

    access_token = await _ensure_valid_token(session_data, session_id)
    if not access_token:
        raise HTTPException(status_code=401, detail="Token refresh failed")

    # Fetch user info from Keycloak
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            settings.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Failed to fetch user info")

    user_info = resp.json()

    # Session rotation (prevents session fixation)
    new_session_id = session_mgr.rotate_session(session_id)
    if not new_session_id:
        # Rotation failed (session disappeared mid-request) — force re-auth
        raise HTTPException(status_code=401, detail="Session lost during rotation")

    response = JSONResponse(content={
        "sub": user_info.get("sub"),
        "username": user_info.get("preferred_username"),
        "email": user_info.get("email"),
        "name": user_info.get("name"),
        "roles": user_info.get("realm_access", {}).get("roles", []),
    })
    _set_session_cookie(response, new_session_id)
    return response


@app.post("/auth/logout")
async def logout(request: Request):
    """Log out: revoke tokens, destroy session, clear cookie."""
    session_id = _get_session_id(request)
    if session_id:
        session_data = session_mgr.get_session(session_id)
        if session_data:
            # Revoke session at Keycloak
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        settings.logout_url,
                        data={
                            "client_id": settings.CLIENT_ID,
                            "client_secret": settings.CLIENT_SECRET,
                            "refresh_token": session_data["refresh_token"],
                        },
                    )
            except Exception:
                pass  # Best-effort logout at IdP
        session_mgr.delete_session(session_id)

    response = JSONResponse(content={"status": "logged_out"})
    _clear_session_cookie(response)
    return response


# ---------------------------------------------------------------------------
# API proxy endpoints
# ---------------------------------------------------------------------------

@app.get("/api/reports")
async def proxy_reports(request: Request):
    """Proxy report requests to reports-api, injecting Bearer token."""
    session_id = _get_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = session_mgr.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=401, detail="Session expired")

    access_token = await _ensure_valid_token(session_data, session_id)
    if not access_token:
        raise HTTPException(status_code=401, detail="Token refresh failed")

    # Forward query params
    query_params = dict(request.query_params)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.REPORTS_API_URL}/reports",
            params=query_params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )

    # Session rotation (prevents session fixation)
    new_session_id = session_mgr.rotate_session(session_id)
    if not new_session_id:
        raise HTTPException(status_code=401, detail="Session lost during rotation")

    response = Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )
    _set_session_cookie(response, new_session_id)
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}
