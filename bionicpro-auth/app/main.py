import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.cors import CORSMiddleware

from . import keycloak_client, pkce
from .config import settings
from .jwt_utils import decode_claims_unverified
from .session_store import (
    SessionData,
    create_session,
    delete_session,
    encrypt_refresh_token,
    decrypt_refresh_token,
    get_session,
    now,
    pop_pkce_verifier,
    store_pkce_verifier,
)

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
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_seconds,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")


async def _persist_tokens(token_response: keycloak_client.TokenResponse) -> str:
    claims = decode_claims_unverified(token_response.access_token)
    data = SessionData(
        sub=claims.get("sub", ""),
        username=claims.get("preferred_username", ""),
        access_token=token_response.access_token,
        access_expires_at=token_response.access_expires_at,
        refresh_token_encrypted=encrypt_refresh_token(token_response.refresh_token),
        refresh_expires_at=token_response.refresh_expires_at,
    )
    session_id = pkce.generate_session_id()
    await create_session(session_id, data)
    return session_id


async def require_valid_session(request: Request, response: Response) -> SessionData:
    """Проверяет сессионную cookie, при необходимости обновляет access_token
    и перепривязывает сессию к новому session id при каждой успешной проверке
    защищённого ресурса (предотвращает session fixation attack).
    """
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    data = await get_session(session_id)
    if data is None:
        raise HTTPException(status_code=401, detail="Session expired or unknown")

    if now() >= data.access_expires_at - settings.access_token_refresh_margin_seconds:
        refresh_token = decrypt_refresh_token(data.refresh_token_encrypted)
        try:
            token_response = await keycloak_client.refresh_tokens(refresh_token)
        except httpx.HTTPStatusError:
            await delete_session(session_id)
            raise HTTPException(status_code=401, detail="Session could not be refreshed")
        claims = decode_claims_unverified(token_response.access_token)
        data = SessionData(
            sub=claims.get("sub", ""),
            username=claims.get("preferred_username", ""),
            access_token=token_response.access_token,
            access_expires_at=token_response.access_expires_at,
            refresh_token_encrypted=encrypt_refresh_token(token_response.refresh_token),
            refresh_expires_at=token_response.refresh_expires_at,
        )

    new_session_id = pkce.generate_session_id()
    await create_session(new_session_id, data)
    await delete_session(session_id)
    _set_session_cookie(response, new_session_id)

    return data


@app.get("/login")
async def login():
    state = pkce.generate_state()
    code_verifier = pkce.generate_code_verifier()
    code_challenge = pkce.derive_code_challenge(code_verifier)
    await store_pkce_verifier(state, code_verifier)
    return RedirectResponse(keycloak_client.build_authorization_url(state, code_challenge))


@app.get("/callback")
async def callback(request: Request):
    error = request.query_params.get("error")
    if error:
        raise HTTPException(status_code=400, detail=f"Identity provider error: {error}")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    code_verifier = await pop_pkce_verifier(state)
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Unknown or expired state")

    token_response = await keycloak_client.exchange_code_for_tokens(code, code_verifier)
    session_id = await _persist_tokens(token_response)

    redirect = RedirectResponse(settings.frontend_url)
    _set_session_cookie(redirect, session_id)
    return redirect


@app.get("/me")
async def me(request: Request, response: Response):
    # Возврат обычного dict (а не нового JSONResponse) позволяет FastAPI
    # слить заголовки/cookie, которые require_valid_session выставил на
    # внедрённый объект `response`, в фактически отправляемый ответ.
    data = await require_valid_session(request, response)
    return {"sub": data.sub, "username": data.username}


@app.post("/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        data = await get_session(session_id)
        if data:
            await keycloak_client.revoke_refresh_token(decrypt_refresh_token(data.refresh_token_encrypted))
        await delete_session(session_id)
    _clear_session_cookie(response)
    return {"status": "logged_out"}


_HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "cookie",
}


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_to_reports_api(path: str, request: Request, response: Response):
    """Backend-for-frontend прокси: браузер никогда не видит access_token,
    он лишь предъявляет сессионную cookie. Этот эндпоинт подставляет
    хранящийся на сервере access_token перед проксированием вызова в reports-api.
    """
    data = await require_valid_session(request, response)

    body = await request.body()
    forward_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS
    }
    forward_headers["Authorization"] = f"Bearer {data.access_token}"

    async with httpx.AsyncClient() as client:
        upstream = await client.request(
            method=request.method,
            url=f"{settings.reports_api_url}/{path}",
            params=request.query_params,
            content=body,
            headers=forward_headers,
            timeout=30.0,
        )

    proxied = Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )
    rotated_cookie = response.headers.get("set-cookie")
    if rotated_cookie:
        proxied.headers["set-cookie"] = rotated_cookie
    return proxied


@app.get("/health")
async def health():
    return {"status": "ok"}
