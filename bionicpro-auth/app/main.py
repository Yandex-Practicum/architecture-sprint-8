import secrets
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from jose import jwt

from . import keycloak_client as kc
from . import session_store as store
from .config import settings

app = FastAPI(title="bionicpro-auth")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def _claims(access_token: str) -> dict:
    """Подпись access_token уже проверена Keycloak при выдаче — повторно не проверяем."""
    return jwt.get_unverified_claims(access_token)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/auth/login")
async def login():
    code_verifier, code_challenge = kc.generate_pkce_pair()
    state = secrets.token_urlsafe(32)
    await store.save_oauth_state(state, code_verifier)
    return RedirectResponse(kc.build_authorization_url(state, code_challenge))


@app.get("/auth/callback")
async def callback(code: str, state: str):
    code_verifier = await store.pop_oauth_state(state)
    if code_verifier is None:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    try:
        tokens = await kc.exchange_code(code, code_verifier)
    except Exception:
        raise HTTPException(status_code=401, detail="Token exchange failed")

    session_id = await store.create_session(tokens)
    response = RedirectResponse(settings.frontend_url)
    _set_session_cookie(response, session_id)
    return response


async def _resolve_and_rotate(request: Request) -> tuple[dict, str, str]:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(status_code=401, detail="No session")

    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Session expired")

    if session["access_expires_at"] <= time.time():
        try:
            tokens = await kc.refresh_tokens(session["refresh_token"])
        except Exception:
            await store.delete_session(session_id)
            raise HTTPException(status_code=401, detail="Refresh failed")
    else:
        tokens = {
            "access_token": session["access_token"],
            "refresh_token": session["refresh_token"],
            "id_token": session["id_token"],
            "expires_in": int(session["access_expires_at"] - time.time()),
        }

    new_session_id = await store.rotate_session(session_id, tokens)
    return _claims(tokens["access_token"]), tokens["access_token"], new_session_id


@app.get("/auth/me")
async def me(request: Request):
    claims, _access, new_session_id = await _resolve_and_rotate(request)
    response = JSONResponse(
        {
            "sub": claims.get("sub"),
            "username": claims.get("preferred_username"),
            "email": claims.get("email"),
            "roles": claims.get("realm_access", {}).get("roles", []),
        }
    )
    _set_session_cookie(response, new_session_id)
    return response


@app.get("/auth/validate")
async def validate(request: Request):
    """new_session_id возвращается в теле, а не cookie: его проставит reports-api
    в своём ответе фронтенду."""
    claims, _access, new_session_id = await _resolve_and_rotate(request)
    response = JSONResponse(
        {
            "sub": claims.get("sub"),
            "username": claims.get("preferred_username"),
            "roles": claims.get("realm_access", {}).get("roles", []),
            "new_session_id": new_session_id,
        }
    )
    return response


@app.post("/auth/logout")
async def logout(request: Request):
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        session = await store.get_session(session_id)
        if session:
            try:
                await kc.logout(session["refresh_token"])
            except Exception:
                pass
        await store.delete_session(session_id)
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie(settings.session_cookie_name, path="/")
    return response
