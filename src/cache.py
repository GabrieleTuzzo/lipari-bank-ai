from functools import cache

from redis.asyncio import Redis

from src.config import settings


@cache
def get_redis() -> Redis | None:
    """Il client Redis condiviso dal processo, oppure None se Redis non è configurato."""
    if not settings.redis_url:
        return None
    return Redis.from_url(
        settings.redis_url,
        socket_timeout=0.5,
        socket_connect_timeout=0.5,
    )


async def chiudi_redis() -> None:
    if (redis := get_redis()) is not None:
        await redis.aclose()
