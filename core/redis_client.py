from functools import lru_cache

from redis.asyncio import Redis

from core.config import settings


@lru_cache(maxsize=1)
def _client() -> Redis:
    return Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )


def get_redis() -> Redis:
    """Зависимость FastAPI: общий асинхронный клиент Redis."""
    return _client()


async def close_redis() -> None:
    await _client().aclose()
    _client.cache_clear()
