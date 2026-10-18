from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyCookie
from redis.asyncio import Redis

from core.config import settings
from core.redis_client import get_redis
from services.session_service import SessionData, SessionService

CURRENT_USER_ID = 1

cookie_scheme = APIKeyCookie(
    name=settings.SESSION_COOKIE_NAME,
    auto_error=False,
    description="Сессионная кука, выдаётся методом POST /api/users/login",
)


async def get_current_session(
    session_id: str | None = Depends(cookie_scheme),
    redis: Redis = Depends(get_redis),
) -> SessionData:
    session = await SessionService(redis).get(session_id)
    if session is None:
        raise HTTPException(401, "Требуется авторизация")
    return session


async def get_current_user_id(session: SessionData = Depends(get_current_session)) -> int:
    return session.user_id


async def get_optional_user_id(
    request: Request,
    redis: Redis = Depends(get_redis),
) -> int | None:
    session = await SessionService(redis).get(request.cookies.get(settings.SESSION_COOKIE_NAME))
    return session.user_id if session else None
