import secrets
from dataclasses import dataclass

from redis.asyncio import Redis

from core.config import settings

KEY_PREFIX = "session:"


@dataclass(frozen=True)
class SessionData:
    session_id: str
    user_id: int
    username: str


class SessionService:

    def __init__(self, redis: Redis):
        self.redis = redis

    @staticmethod
    def _key(session_id: str) -> str:
        return f"{KEY_PREFIX}{session_id}"

    async def create(self, user_id: int, username: str) -> str:
        session_id = secrets.token_urlsafe(32)
        key = self._key(session_id)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(key, mapping={"user_id": user_id, "username": username})
            pipe.expire(key, settings.SESSION_TTL_SECONDS)
            await pipe.execute()
        return session_id

    async def get(self, session_id: str | None) -> SessionData | None:
        if not session_id:
            return None
        data = await self.redis.hgetall(self._key(session_id))
        if not data or "user_id" not in data:
            return None
        return SessionData(session_id, int(data["user_id"]), data.get("username", ""))

    async def delete(self, session_id: str) -> None:
        await self.redis.delete(self._key(session_id))
