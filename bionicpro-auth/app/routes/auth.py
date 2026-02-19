from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from app.services.keycloak import keycloak_client
from app.services.session import (
    create_session,
    get_session,
    delete_session,
    SessionData,
)
from app.dependencies import get_current_session
from app.config import settings
import uuid
import secrets
from keycloak import KeycloakOpenID

keycloak_openid = KeycloakOpenID(
    server_url=settings.keycloak_url,
    realm_name=settings.keycloak_realm,
    client_id=settings.client_id,
)

router = APIRouter(prefix="/auth", tags=["auth"])

pending_states = {}


@router.get("/login")
async def login(request: Request):
    """Начинает OAuth2 flow с PKCE, редиректит на Keycloak"""
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = keycloak_client.generate_pkce_pair()
    request.session["oauth_state"] = state
    request.session["code_verifier"] = code_verifier
    pending_states[state] = (code_verifier, settings.frontend_url)
    auth_url = keycloak_client.get_authorization_url(state, code_challenge)
    return RedirectResponse(auth_url)


@router.get("/callback")
async def callback(request: Request, code: str, state: str):
    """Эндпоинт, куда Keycloak редиректит после логина"""
    if state not in pending_states:
        raise HTTPException(status_code=400, detail="Invalid state")
    code_verifier, frontend_url = pending_states.pop(state)

    try:
        token_data = await keycloak_client.exchange_code(code, code_verifier)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Token exchange failed")

    userinfo = await keycloak_client.get_userinfo(token_data["access_token"])
    user_id = userinfo["sub"]

    session_id = str(uuid.uuid4())
    session = SessionData(
        user_id=user_id,
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data.get("expires_in", 120),
        id_token=token_data.get("id_token"),
    )
    await create_session(session_id, session)

    response = RedirectResponse(url=frontend_url)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.session_ttl,
    )
    return response


@router.get("/logout/callback")
async def logout_callback(request: Request):
    frontend_url = settings.frontend_url
    return RedirectResponse(frontend_url)


@router.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    id_token_hint = None

    if session_id:
        session_data = await get_session(session_id)
        if session_data:
            id_token_hint = session_data.id_token

        await delete_session(session_id)

    logout_url = keycloak_client.get_logout_url(id_token_hint=id_token_hint)

    response = RedirectResponse(url=logout_url)
    response.delete_cookie("session_id")

    return response


@router.get("/me")
async def me(session=Depends(get_current_session)):
    return {"user_id": session.user_id}


@router.get("/userinfo")
async def userinfo(session=Depends(get_current_session)):
    userinfo = keycloak_openid.userinfo(session.access_token)
    return {
        "email": userinfo.get("email"),
        "firstName": userinfo.get("given_name"),
        "lastName": userinfo.get("family_name"),
    }
