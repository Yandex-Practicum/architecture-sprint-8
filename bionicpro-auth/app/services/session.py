import json
import redis.asyncio as redis
from typing import Optional
from datetime import datetime, timedelta
from app.config import settings
from app.services.crypto import encrypt_token, decrypt_token

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

class SessionData:
    def __init__(self, user_id: str, access_token: str, refresh_token: str, expires_in: int, id_token: str = None):
        self.user_id = user_id
        self.access_token = access_token
        self.refresh_token_enc = encrypt_token(refresh_token)
        self.expires_at = datetime.now() + timedelta(seconds=expires_in)
        self.id_token = id_token

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "access_token": self.access_token,
            "id_token": self.id_token,
            "refresh_token_enc": self.refresh_token_enc,
            "expires_at": self.expires_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls(
            user_id=data["user_id"],
            access_token=data["access_token"],
            refresh_token="",
            id_token=data.get("id_token"),
            expires_in=0
        )
        obj.refresh_token_enc = data["refresh_token_enc"]
        obj.expires_at = datetime.fromisoformat(data["expires_at"])
        return obj

    def get_refresh_token(self) -> str:
        return decrypt_token(self.refresh_token_enc)

async def create_session(session_id: str, data: SessionData):
    await redis_client.setex(
        f"session:{session_id}",
        settings.session_ttl,
        json.dumps(data.to_dict())
    )

async def get_session(session_id: str) -> Optional[SessionData]:
    data = await redis_client.get(f"session:{session_id}")
    if data:
        return SessionData.from_dict(json.loads(data))
    return None

async def delete_session(session_id: str):
    await redis_client.delete(f"session:{session_id}")

async def rotate_session(old_sid: str, new_sid: str, data: SessionData):
    """Перепривязывает данные к новому session_id и удаляет старый"""
    await create_session(new_sid, data)
    await delete_session(old_sid)

async def update_session_tokens(session_id: str, new_access: str, new_refresh: str, expires_in: int):
    data = await get_session(session_id)
    if data:
        data.access_token = new_access
        data.refresh_token_enc = encrypt_token(new_refresh)
        data.expires_at = datetime.now() + timedelta(seconds=expires_in)
        await create_session(session_id, data)