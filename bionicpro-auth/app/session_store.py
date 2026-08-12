import json
import time
from dataclasses import dataclass, asdict
from typing import Optional

import redis.asyncio as redis
from cryptography.fernet import Fernet

from .config import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)
_fernet = Fernet(settings.token_encryption_key.encode("ascii"))

_PKCE_PREFIX = "bpro:pkce:"
_SESSION_PREFIX = "bpro:session:"
_PKCE_TTL_SECONDS = 300


@dataclass
class SessionData:
    sub: str
    username: str
    access_token: str
    access_expires_at: float
    refresh_token_encrypted: str
    refresh_expires_at: float

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(raw: str) -> "SessionData":
        return SessionData(**json.loads(raw))


def encrypt_refresh_token(refresh_token: str) -> str:
    return _fernet.encrypt(refresh_token.encode("utf-8")).decode("ascii")


def decrypt_refresh_token(token_encrypted: str) -> str:
    return _fernet.decrypt(token_encrypted.encode("ascii")).decode("utf-8")


async def store_pkce_verifier(state: str, code_verifier: str) -> None:
    await _redis.set(_PKCE_PREFIX + state, code_verifier, ex=_PKCE_TTL_SECONDS)


async def pop_pkce_verifier(state: str) -> Optional[str]:
    key = _PKCE_PREFIX + state
    value = await _redis.get(key)
    if value is not None:
        await _redis.delete(key)
    return value


async def create_session(session_id: str, data: SessionData) -> None:
    await _redis.set(_SESSION_PREFIX + session_id, data.to_json(), ex=settings.session_ttl_seconds)


async def get_session(session_id: str) -> Optional[SessionData]:
    raw = await _redis.get(_SESSION_PREFIX + session_id)
    if raw is None:
        return None
    return SessionData.from_json(raw)


async def delete_session(session_id: str) -> None:
    await _redis.delete(_SESSION_PREFIX + session_id)


def now() -> float:
    return time.time()
