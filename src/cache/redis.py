import json
import logging
import time
from typing import Any, Optional, TypeVar, Union, cast

import redis.asyncio as redis
from pydantic import BaseModel

from src.config import settings


logger = logging.getLogger(__name__)

# Create a type variable for generic cache type
T = TypeVar("T", bound=BaseModel)


class RedisClient:
    """Redis client for caching with connection retries."""

    def __init__(self) -> None:
        self.redis_url = str(settings.REDIS_URL)
        self.client: Optional[redis.Redis] = None
        self.default_ttl = settings.CACHE_TTL
        self.max_retries = 3
        self.retry_delay = 0.5

    async def connect(self, retry: bool = True) -> Optional[redis.Redis]:
        """
        Connect to Redis with retry support.

        Args:
            retry: Whether to retry connection on failure

        Returns:
            Redis client or None if connection failed
        """
        if self.client is not None:
            return self.client

        retries = 0
        last_error = None

        while retries <= self.max_retries:
            try:
                self.client = redis.from_url(  # type: ignore[no-untyped-call]
                    self.redis_url, decode_responses=True
                )

                # Test connection with a ping
                if await self.client.ping():
                    logger.info("Connected to Redis successfully")
                    return self.client
                else:
                    logger.warning("Redis ping failed, reconnecting...")

            except (redis.ConnectionError, redis.TimeoutError) as e:
                last_error = e
                if not retry or retries >= self.max_retries:
                    break

                retries += 1
                wait_time = self.retry_delay * (
                    2**retries
                )  # Exponential backoff
                logger.warning(
                    "Failed to connect to Redis (attempt %s/%s): %s. "
                    "Retrying in %.2f seconds...",
                    retries,
                    self.max_retries,
                    str(e),
                    wait_time,
                )
                time.sleep(wait_time)

            except Exception as e:
                last_error = e
                logger.error("Unexpected error connecting to Redis: %s", e)
                break

        # If we got here, connection failed
        if last_error:
            logger.error(
                "Failed to connect to Redis after %s attempts: %s",
                retries,
                last_error,
            )
        else:
            logger.error(
                "Failed to connect to Redis after %s attempts", retries
            )

        return None

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.client:
            try:
                await self.client.close()
                self.client = None
                logger.info("Disconnected from Redis")
            except Exception as e:
                logger.error("Error disconnecting from Redis: %s", e)

    async def get(self, key: str) -> Optional[str]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or error
        """
        client = await self.connect()
        if not client:
            logger.warning(
                "Redis connection not available, skipping cache get"
            )
            return None

        try:
            return await client.get(key)
        except Exception as e:
            logger.warning("Error getting value from Redis: %s", e)
            return None

    async def set(
        self, key: str, value: str, ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if value was set, False otherwise
        """
        client = await self.connect()
        if not client:
            logger.warning(
                "Redis connection not available, skipping cache set"
            )
            return False

        try:
            return bool(
                await client.set(key, value, ex=ttl or self.default_ttl)
            )
        except Exception as e:
            logger.warning("Error setting value in Redis: %s", e)
            return False

    async def delete(self, key: str) -> int:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            Number of keys deleted
        """
        client = await self.connect()
        if not client:
            logger.warning(
                "Redis connection not available, skipping cache delete"
            )
            return 0

        try:
            return await client.delete(key)
        except Exception as e:
            logger.warning("Error deleting key from Redis: %s", e)
            return 0

    async def get_object(
        self, key: str, model_class: Optional[type[T]] = None
    ) -> Optional[Union[dict[str, Any], T]]:
        """
        Get object from cache and deserialize it.

        Args:
            key: Cache key
            model_class: Optional Pydantic model class to deserialize into

        Returns:
            Deserialized object or None if not found or error
        """
        json_str = await self.get(key)
        if not json_str:
            return None

        try:
            data = json.loads(json_str)
            if model_class:
                try:
                    # For Pydantic v2
                    return model_class.model_validate(data)
                except AttributeError:
                    # For Pydantic v1
                    return model_class.parse_obj(data)
            return cast(dict[str, Any], data)
        except Exception as e:
            logger.warning("Error deserializing object from Redis: %s", e)
            return None

    async def set_object(
        self,
        key: str,
        value: Union[dict[str, Any], BaseModel],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Serialize object and set in cache with TTL.

        Args:
            key: Cache key
            value: Object to serialize and cache
            ttl: Time-to-live in seconds

        Returns:
            True if object was cached, False otherwise
        """
        try:
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
        except Exception as e:
            logger.warning("Error serializing object for Redis: %s", e)
            return False


# Initialize global client instance
redis_client = RedisClient()
