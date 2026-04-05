import json

from redis.asyncio import Redis

from settings import Settings


class RedisStore:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._r = redis
        self._s = settings

    def _pkce_key(self, state: str) -> str:
        return f"{self._s.pkce_key_prefix}{state}"

    def _session_key(self, session_id: str) -> str:
        return f"{self._s.session_key_prefix}{session_id}"

    async def save_pkce_verifier(self, state: str, code_verifier: str) -> None:
        await self._r.set(
            self._pkce_key(state),
            code_verifier,
            ex=self._s.pkce_ttl_seconds,
        )

    async def pop_pkce_verifier(self, state: str) -> str | None:
        key = self._pkce_key(state)
        raw = await self._r.get(key)
        if raw is not None:
            await self._r.delete(key)
        return raw

    async def get_session_raw(self, session_id: str) -> str | None:
        return await self._r.get(self._session_key(session_id))

    async def delete_session(self, session_id: str) -> None:
        await self._r.delete(self._session_key(session_id))

    async def save_session(self, session_id: str, payload: dict) -> None:
        await self._r.set(
            self._session_key(session_id),
            json.dumps(payload),
            ex=self._s.session_ttl_seconds,
        )

    async def rotate_session(self, old_id: str, new_id: str, payload: dict) -> None:
        await self.save_session(new_id, payload)
        await self.delete_session(old_id)
