import json
import logging
from typing import Any, Optional, TypeVar, Union, cast

import redis.asyncio as redis
from pydantic import BaseModel

from src.config import settings


logger = logging.getLogger(__name__)

# Create a type variable for generic cache type
T = TypeVar("T", bound=BaseModel)


class RedisClient:
    """Redis client for caching."""

    def __init__(self) -> None:
        self.redis_url = str(settings.REDIS_URL)
        self.client: Optional[redis.Redis] = None
        self.default_ttl = settings.CACHE_TTL

    async def connect(self) -> redis.Redis:
        """Connect to Redis."""
        if self.client is None:
            self.client = redis.from_url(  # type: ignore[no-untyped-call]
                self.redis_url, decode_responses=True
            )
            logger.info("Connected to Redis")
        return self.client

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("Disconnected from Redis")

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        client = await self.connect()
        return await client.get(key)

    async def set(
        self, key: str, value: str, ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with TTL."""
        client = await self.connect()
        return bool(await client.set(key, value, ex=ttl or self.default_ttl))

    async def delete(self, key: str) -> int:
        """Delete key from cache."""
        client = await self.connect()
        return await client.delete(key)

    async def get_object(
        self, key: str, model_class: Optional[type[T]] = None
    ) -> Optional[Union[dict[str, Any], T]]:
        """Get object from cache and deserialize it."""
        json_str = await self.get(key)
        if not json_str:
            return None

        data = json.loads(json_str)
        if model_class:
            try:
                # For Pydantic v2
                return model_class.model_validate(data)
            except AttributeError:
                # For Pydantic v1
                return model_class.parse_obj(data)
        return cast(dict[str, Any], data)

    async def set_object(
        self,
        key: str,
        value: Union[dict[str, Any], BaseModel],
        ttl: Optional[int] = None,
    ) -> bool:
        """Serialize object and set in cache with TTL."""
        if isinstance(value, BaseModel):
            # Handle both Pydantic v1 and v2
            try:
                value_dict = value.model_dump()
            except AttributeError:
                value_dict = value.dict()
        else:
            value_dict = value

        json_str = json.dumps(value_dict)
        return await self.set(key, json_str, ttl)


redis_client = RedisClient()
