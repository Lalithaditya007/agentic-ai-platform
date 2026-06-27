import redis.asyncio as aioredis
from config import settings

_redis_client = None


async def init_redis():
    """Initialize the Redis connection (Upstash cloud)."""
    global _redis_client
    _redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    # Test connection
    await _redis_client.ping()


def get_redis() -> aioredis.Redis:
    """Get the Redis client instance."""
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client


# ── Helper methods ────────────────────────────────────────

async def redis_get(key: str) -> str | None:
    return await get_redis().get(key)


async def redis_set(key: str, value: str, ttl_seconds: int = None):
    if ttl_seconds:
        await get_redis().setex(key, ttl_seconds, value)
    else:
        await get_redis().set(key, value)


async def redis_delete(key: str):
    await get_redis().delete(key)


async def redis_exists(key: str) -> bool:
    return bool(await get_redis().exists(key))


# ── TTL Constants (per implementation plan Section 21) ────
TTL_COMPANY_DOMAIN = 7 * 24 * 3600     # 7 days
TTL_CONTACT = 3 * 24 * 3600            # 3 days
TTL_WORKFLOW_RUN = 24 * 3600            # 24 hours
TTL_PLANNER_SEEN = 30 * 24 * 3600      # 30 days
TTL_TRIGGER_FEED = 6 * 3600            # 6 hours
