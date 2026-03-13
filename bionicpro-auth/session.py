import json
import secrets
import time
from typing import Optional

import redis

from config import settings

_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

SESSION_PREFIX = "session:"
PKCE_PREFIX = "pkce:"


def _session_key(session_id: str) -> str:
    return f"{SESSION_PREFIX}{session_id}"


def _pkce_key(state: str) -> str:
    return f"{PKCE_PREFIX}{state}"


def generate_session_id() -> str:
    return secrets.token_urlsafe(32)


# --- PKCE state management ---

def store_pkce_verifier(state: str, code_verifier: str, ttl: int = 600) -> None:
    """Store PKCE code_verifier keyed by OAuth state param. TTL = 10 min."""
    _redis.setex(_pkce_key(state), ttl, code_verifier)


def get_pkce_verifier(state: str) -> Optional[str]:
    """Retrieve and delete PKCE code_verifier for the given state."""
    key = _pkce_key(state)
    verifier = _redis.get(key)
    if verifier:
        _redis.delete(key)
    return verifier


# --- Session management ---

def create_session(
    access_token: str,
    refresh_token: str,
    expires_in: int,
    id_token: Optional[str] = None,
) -> str:
    """Create a new session storing tokens in Redis. Returns session_id."""
    session_id = generate_session_id()
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token or "",
        "expires_at": time.time() + expires_in,
        "created_at": time.time(),
    }
    _redis.setex(
        _session_key(session_id),
        settings.SESSION_MAX_AGE,
        json.dumps(data),
    )
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    """Retrieve session data from Redis."""
    raw = _redis.get(_session_key(session_id))
    if raw is None:
        return None
    return json.loads(raw)


def update_session(session_id: str, data: dict) -> None:
    """Update session data in Redis, preserving TTL."""
    ttl = _redis.ttl(_session_key(session_id))
    if ttl and ttl > 0:
        _redis.setex(_session_key(session_id), ttl, json.dumps(data))


def rotate_session(old_session_id: str) -> Optional[str]:
    """
    Session rotation: create a new session ID, migrate data, delete old.
    Prevents session fixation attacks.
    """
    data = get_session(old_session_id)
    if data is None:
        return None

    new_session_id = generate_session_id()
    _redis.setex(
        _session_key(new_session_id),
        settings.SESSION_MAX_AGE,
        json.dumps(data),
    )
    _redis.delete(_session_key(old_session_id))
    return new_session_id


def delete_session(session_id: str) -> None:
    """Delete session from Redis."""
    _redis.delete(_session_key(session_id))
