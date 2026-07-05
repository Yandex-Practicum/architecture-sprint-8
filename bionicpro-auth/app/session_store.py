import json
import secrets
import time

import redis.asyncio as redis
from cryptography.fernet import Fernet

from .config import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)
_fernet = Fernet(settings.encryption_key.encode())

_SESSION_PREFIX = "session:"
_STATE_PREFIX = "oauthstate:"


def _session_key(session_id: str) -> str:
    return f"{_SESSION_PREFIX}{session_id}"


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


async def save_oauth_state(state: str, code_verifier: str, ttl: int = 300) -> None:
    await _redis.set(f"{_STATE_PREFIX}{state}", code_verifier, ex=ttl)


async def pop_oauth_state(state: str) -> str | None:
    key = f"{_STATE_PREFIX}{state}"
    verifier = await _redis.get(key)
    if verifier is not None:
        await _redis.delete(key)
    return verifier


async def create_session(tokens: dict) -> str:
    session_id = new_session_id()
    await _write_session(session_id, tokens)
    return session_id


async def _write_session(session_id: str, tokens: dict) -> None:
    payload = {
        "access_token": tokens["access_token"],
        "refresh_token_enc": _fernet.encrypt(tokens["refresh_token"].encode()).decode(),
        "id_token": tokens.get("id_token", ""),
        "access_expires_at": time.time() + int(tokens.get("expires_in", 0)),
    }
    await _redis.set(
        _session_key(session_id), json.dumps(payload), ex=settings.session_ttl_seconds
    )


async def get_session(session_id: str) -> dict | None:
    raw = await _redis.get(_session_key(session_id))
    if raw is None:
        return None
    data = json.loads(raw)
    data["refresh_token"] = _fernet.decrypt(data["refresh_token_enc"].encode()).decode()
    return data


async def update_tokens(session_id: str, tokens: dict) -> None:
    await _write_session(session_id, tokens)


async def rotate_session(old_session_id: str, tokens: dict) -> str:
    """Смена session_id — защита от session fixation."""
    new_id = new_session_id()
    await _write_session(new_id, tokens)
    await _redis.delete(_session_key(old_session_id))
    return new_id


async def delete_session(session_id: str) -> None:
    await _redis.delete(_session_key(session_id))
