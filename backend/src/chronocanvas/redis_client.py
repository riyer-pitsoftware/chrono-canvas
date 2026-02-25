import json
from typing import Any

import redis.asyncio as redis

from chronocanvas.config import settings


async def get_redis() -> redis.Redis:
    """Return the shared async Redis client from the service registry."""
    from chronocanvas.service_registry import get_registry

    reg = get_registry()
    if reg.redis is None:
        reg.redis = redis.from_url(settings.redis_url, decode_responses=True)
    return reg.redis


async def close_redis() -> None:
    from chronocanvas.service_registry import get_registry

    reg = get_registry()
    if reg.redis is not None:
        await reg.redis.close()
        reg.redis = None


async def publish_progress(channel: str, data: dict[str, Any]) -> None:
    r = await get_redis()
    await r.publish(channel, json.dumps(data))


async def subscribe(channel: str):
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    return pubsub
