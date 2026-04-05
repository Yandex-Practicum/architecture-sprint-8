import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
from redis.asyncio import Redis, from_url
from starlette.responses import RedirectResponse, Response

from jwt_claims import make_jwks_client, preferred_username_from_access_token
from keycloak import KeycloakClient
from redis_store import RedisStore
from settings import settings
from utils import Pkce, SessionContext, random_urlsafe_token

logger = logging.getLogger(__name__)


async def require_session(request: Request, response: Response) -> SessionContext:
    store: RedisStore = request.app.state.redis_store
    keycloak: KeycloakClient = request.app.state.keycloak
    old_session_id = request.cookies.get(settings.cookie_name)
    if not old_session_id:
        raise HTTPException(status_code=401, detail="not authenticated")

    raw = await store.get_session_raw(old_session_id)
    if not raw:
        raise HTTPException(status_code=401, detail="invalid session")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="invalid session")

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token") or ""
    access_expires_at = int(payload.get("access_expires_at", 0))
    now = int(time.time())

    if not access_token:
        raise HTTPException(status_code=401, detail="invalid session")

    token_refreshed = False
    if now >= access_expires_at - settings.access_token_refresh_skew_seconds:
        if not refresh_token:
            await store.delete_session(old_session_id)
            raise HTTPException(status_code=401, detail="session expired")
        token_data = await keycloak.refresh(refresh_token)
        access_token = token_data.get("access_token")
        if not access_token:
            await store.delete_session(old_session_id)
            raise HTTPException(status_code=401, detail="session expired")
        refresh_token = token_data.get("refresh_token") or refresh_token
        expires_in = int(token_data.get("expires_in", 300))
        access_expires_at = int(time.time()) + expires_in
        payload = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "access_expires_at": access_expires_at,
        }
        token_refreshed = True

    # Rotating the session id on every request breaks parallel /reports calls
    # (e.g. React Strict Mode): the second in-flight request still sends the old
    # cookie while Redis already deleted that key. Rotate only when tokens change.
    session_cookie_value = old_session_id
    if token_refreshed:
        session_cookie_value = random_urlsafe_token()
        await store.rotate_session(old_session_id, session_cookie_value, payload)
    else:
        await store.save_session(old_session_id, payload)

    response.set_cookie(
        key=settings.cookie_name,
        value=session_cookie_value,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_seconds,
        path="/",
    )

    return SessionContext(access_token=access_token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis: Redis = from_url(
        settings.redis_url,
        decode_responses=True,
        encoding="utf-8",
    )
    app.state.redis_store = RedisStore(redis, settings)
    app.state.keycloak = KeycloakClient(settings)
    app.state.jwks_client = make_jwks_client(settings)
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    try:
        yield
    finally:
        await app.state.http_client.aclose()
        await redis.aclose()


app = FastAPI(title="bionicpro-auth", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url.rstrip("/")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/reports")
async def reports(
    request: Request,
    session: Annotated[SessionContext, Depends(require_session)],
):
    user_id = preferred_username_from_access_token(
        request.app.state.jwks_client,
        settings,
        session.access_token,
    )
    url = f"{settings.reports_api_base_url}/reports"
    client: httpx.AsyncClient = request.app.state.http_client
    try:
        upstream = await client.get(url, headers={"X-User-Id": user_id})
    except httpx.RequestError as e:
        logger.exception("reports-api request failed: %s", e)
        raise HTTPException(
            status_code=502, detail="reports service unreachable"
        ) from e

    media_type = upstream.headers.get("content-type") or "application/json"
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=media_type,
    )


@app.get("/auth/login")
async def auth_login(request: Request):
    store: RedisStore = request.app.state.redis_store
    keycloak: KeycloakClient = request.app.state.keycloak
    state = random_urlsafe_token()
    code_verifier = Pkce.generate_verifier()
    code_challenge = Pkce.code_challenge_s256(code_verifier)

    await store.save_pkce_verifier(state, code_verifier)
    url = keycloak.build_authorize_url(state=state, code_challenge=code_challenge)
    return RedirectResponse(url=url, status_code=302)


@app.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    store: RedisStore = request.app.state.redis_store
    keycloak: KeycloakClient = request.app.state.keycloak
    if error:
        logger.warning("Keycloak returned error: %s %s", error, error_description)
        sep = "&" if "?" in settings.frontend_url else "?"
        return RedirectResponse(
            url=f"{settings.frontend_url}{sep}error={quote(error)}",
            status_code=302,
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="missing code or state")

    raw_verifier = await store.pop_pkce_verifier(state)
    if not raw_verifier:
        raise HTTPException(status_code=400, detail="invalid or expired state")

    token_data = await keycloak.exchange_authorization_code(
        code=code, code_verifier=raw_verifier
    )
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="no access_token in response")

    refresh_token = token_data.get("refresh_token") or ""
    expires_in = int(token_data.get("expires_in", 300))
    access_expires_at = int(time.time()) + expires_in

    session_payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_expires_at": access_expires_at,
    }

    session_id = random_urlsafe_token()
    await store.save_session(session_id, session_payload)

    redirect = RedirectResponse(url=settings.frontend_url, status_code=302)
    redirect.set_cookie(
        key=settings.cookie_name,
        value=session_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return redirect
