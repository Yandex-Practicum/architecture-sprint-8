from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from .config import Settings
from .keycloak import KeycloakClient, TokenSet
from .profile_store import ProfileStore
from .session_store import SessionStore, UserSession, utc_now


settings = Settings()
logger = logging.getLogger(__name__)
token_encryption_key = settings.token_encryption_key or base64.urlsafe_b64encode(
    secrets.token_bytes(32)
).decode("utf-8")
session_store = SessionStore(
    encryption_key=token_encryption_key,
    session_ttl_seconds=settings.session_ttl_seconds,
    auth_request_ttl_seconds=settings.auth_request_ttl_seconds,
)
profile_store = ProfileStore(settings.profile_db_path)
keycloak_client = KeycloakClient(settings)


def _code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _parse_token_claims(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))


def _safe_return_to(candidate: str | None) -> str:
    if not candidate:
        return "/"
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return "/"
    return candidate if candidate.startswith("/") else "/"


def _pick_first(*values: Any) -> Any:
    for value in values:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
        elif value is not None:
            return value
    return None


def _merge_profile(
    claims: dict[str, Any],
    userinfo: dict[str, Any],
    identity_provider: str,
    external_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = dict(claims)
    profile.update(userinfo)
    profile["identity_provider"] = identity_provider

    if identity_provider != "yandex" or external_profile is None:
        return profile

    profile.update(external_profile)
    profile["source_profile"] = external_profile
    profile["preferred_username"] = _pick_first(
        profile.get("preferred_username"),
        external_profile.get("login"),
    )
    profile["email"] = _pick_first(
        profile.get("email"),
        external_profile.get("default_email"),
    )
    profile["name"] = _pick_first(
        profile.get("name"),
        external_profile.get("real_name"),
        external_profile.get("display_name"),
    )
    profile["given_name"] = _pick_first(
        profile.get("given_name"),
        external_profile.get("first_name"),
    )
    profile["family_name"] = _pick_first(
        profile.get("family_name"),
        external_profile.get("last_name"),
    )
    return profile


async def _load_profile(token_set: TokenSet, claims: dict[str, Any]) -> dict[str, Any]:
    try:
        userinfo = await keycloak_client.userinfo(token_set.access_token)
    except httpx.HTTPError as error:
        details = ""
        if isinstance(error, httpx.HTTPStatusError):
            details = error.response.text
        logger.warning("Unable to load Keycloak userinfo: %s %s", type(error).__name__, details)
        userinfo = {}

    identity_provider = claims.get("identity_provider") or userinfo.get("identity_provider") or "local"
    external_profile: dict[str, Any] | None = None

    if identity_provider == "yandex":
        try:
            broker_tokens = await keycloak_client.broker_token(
                provider_alias=identity_provider,
                access_token=token_set.access_token,
            )
            external_access_token = broker_tokens.get("access_token")
            if not external_access_token:
                raise HTTPException(status_code=502, detail="Yandex access token is unavailable.")
            external_profile = await keycloak_client.yandex_userinfo(external_access_token)
        except (httpx.HTTPError, ValueError, HTTPException) as error:
            if isinstance(error, httpx.HTTPStatusError):
                details = error.response.text
            else:
                details = str(error)
            logger.error("Unable to load Yandex profile: %s %s", type(error).__name__, details)
            raise HTTPException(status_code=502, detail="Unable to load Yandex profile.") from error

    return _merge_profile(claims, userinfo, identity_provider, external_profile)


def _session_payload(session: UserSession) -> dict[str, Any]:
    return {
        "authenticated": True,
        "user": {
            "sub": session.subject,
            "username": session.username,
            "email": session.email,
            "fullName": session.full_name,
            "roles": list(session.roles),
            "identityProvider": session.identity_provider,
        },
    }


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    response.headers["Cache-Control"] = "no-store"


def _set_auth_flow_cookie(response: Response, state: str) -> None:
    response.set_cookie(
        key=settings.auth_flow_cookie_name,
        value=state,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.auth_request_ttl_seconds,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def _clear_auth_flow_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.auth_flow_cookie_name, path="/")
    response.headers["Cache-Control"] = "no-store"


async def _resolve_authenticated_session(request: Request, response: Response) -> UserSession:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(status_code=401, detail="Session cookie is missing.")

    session = session_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Session is missing or expired.")

    refresh_deadline = utc_now() + timedelta(seconds=settings.access_token_refresh_skew_seconds)
    if session.access_token_expires_at <= refresh_deadline:
        try:
            refreshed = await keycloak_client.refresh_tokens(
                session_store.decrypt_refresh_token(session)
            )
        except httpx.HTTPError as error:
            details = ""
            if isinstance(error, httpx.HTTPStatusError):
                details = error.response.text
            logger.warning("Unable to refresh Keycloak tokens: %s %s", type(error).__name__, details)
            session_store.delete_session(session_id)
            _clear_session_cookie(response)
            raise HTTPException(status_code=401, detail="Unable to refresh session.") from error

        session = session_store.update_session_tokens(session_id, refreshed)
        if session is None:
            raise HTTPException(status_code=401, detail="Session expired during refresh.")

    rotated = session_store.rotate_session(session.session_id)
    if rotated is None:
        raise HTTPException(status_code=401, detail="Session rotation failed.")

    _set_session_cookie(response, rotated.session_id)
    return rotated


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await keycloak_client.close()


app = FastAPI(
    title="bionicpro-auth",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_base_url],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/login")
async def login(return_to: str | None = None) -> RedirectResponse:
    code_verifier = secrets.token_urlsafe(64)
    pending = session_store.create_pending_authorization(
        return_to=_safe_return_to(return_to),
        code_verifier=code_verifier,
    )
    response = RedirectResponse(
        url=keycloak_client.build_authorization_url(
            state=pending.state,
            code_challenge=_code_challenge(code_verifier),
        ),
        status_code=302,
    )
    _set_auth_flow_cookie(response, pending.state)
    return response


@app.get("/auth/callback")
async def auth_callback(code: str, state: str, request: Request) -> RedirectResponse:
    flow_state = request.cookies.get(settings.auth_flow_cookie_name)
    if flow_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state.")

    pending = session_store.pop_pending_authorization(state)
    if pending is None:
        raise HTTPException(status_code=400, detail="Authorization request expired.")

    try:
        token_set = await keycloak_client.exchange_code(code=code, code_verifier=pending.code_verifier)
    except httpx.HTTPError as error:
        details = ""
        if isinstance(error, httpx.HTTPStatusError):
            details = error.response.text
        logger.error("Keycloak authorization failed for callback state=%s: %s %s", state, type(error).__name__, details)
        raise HTTPException(status_code=502, detail="Keycloak authorization failed.") from error

    claims = _parse_token_claims(token_set.access_token)
    profile = await _load_profile(token_set, claims)
    roles = tuple(sorted(claims.get("realm_access", {}).get("roles", [])))
    identity_provider = profile.get("identity_provider") or "local"
    subject = profile.get("sub") or claims.get("sub")
    username = (
        profile.get("preferred_username")
        or profile.get("login")
        or profile.get("email")
        or profile.get("default_email")
        or subject
    )
    if not subject or not username:
        raise HTTPException(status_code=502, detail="User profile from IdP is incomplete.")

    profile_store.upsert(subject=subject, identity_provider=identity_provider, profile=profile)

    session = session_store.create_session(
        token_set=token_set,
        subject=subject,
        username=username,
        email=profile.get("email") or profile.get("default_email"),
        full_name=profile.get("name") or profile.get("real_name") or profile.get("given_name"),
        roles=roles,
        identity_provider=identity_provider,
    )

    response = RedirectResponse(url=pending.return_to or "/", status_code=302)
    _clear_auth_flow_cookie(response)
    _set_session_cookie(response, session.session_id)
    return response


@app.get("/auth/me")
async def me(request: Request, response: Response) -> JSONResponse:
    session = await _resolve_authenticated_session(request, response)
    return JSONResponse(_session_payload(session), headers=dict(response.headers))


@app.get("/internal/session")
async def internal_session(request: Request, response: Response) -> JSONResponse:
    session = await _resolve_authenticated_session(request, response)
    return JSONResponse(_session_payload(session), headers=dict(response.headers))


@app.post("/auth/logout")
async def logout(request: Request, response: Response) -> JSONResponse:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        cleared = JSONResponse({"loggedOut": True})
        _clear_session_cookie(cleared)
        return cleared

    session = session_store.get_session(session_id)
    if session is not None:
        try:
            await keycloak_client.logout(session_store.decrypt_refresh_token(session))
        except httpx.HTTPError:
            pass
        session_store.delete_session(session_id)

    cleared = JSONResponse({"loggedOut": True})
    _clear_session_cookie(cleared)
    return cleared
