from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from starlette.responses import Response
from app.services.session import (
    delete_session,
    get_session,
    rotate_session,
    update_session_tokens,
)
from app.services.keycloak import keycloak_client
from app.config import settings
from app.services.crypto import encrypt_token
import uuid
import time
from jose import jwt


async def get_current_session(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")

    try:
        payload = jwt.get_unverified_claims(session.access_token)
        exp = payload.get("exp")
        if exp and exp < time.time():
            try:
                new_tokens = await keycloak_client.refresh_access_token(
                    session.get_refresh_token()
                )
                session.access_token = new_tokens["access_token"]
                if "refresh_token" in new_tokens:
                    session.refresh_token_enc = encrypt_token(
                        new_tokens["refresh_token"]
                    )
                session.expires_at = datetime.now() + timedelta(
                    seconds=new_tokens.get("expires_in", 120)
                )
                await update_session_tokens(
                    session_id,
                    new_tokens["access_token"],
                    new_tokens.get("refresh_token", session.get_refresh_token()),
                    new_tokens.get("expires_in", 120),
                )
            except Exception:
                await delete_session(session_id)
                raise HTTPException(status_code=401, detail="Session expired")
    except Exception:
        await delete_session(session_id)
        raise HTTPException(status_code=401, detail="Invalid session")

    new_sid = str(uuid.uuid4())
    await rotate_session(session_id, new_sid, session)
    response.set_cookie(
        key="session_id",
        value=new_sid,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.session_ttl,
    )

    return session
