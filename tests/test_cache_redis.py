import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as redis
from pydantic import BaseModel

from src.cache.redis import RedisClient


# Sample Pydantic model for testing
class TestModel(BaseModel):
    id: int
    name: str
    created_at: datetime


class TestRedisClient:
    """Tests for the Redis caching client."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection to Redis."""
        # Arrange
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True

        # Patch redis.from_url to return our mock
        with patch("redis.asyncio.from_url", return_value=mock_redis):
            client = RedisClient()

            # Act
            result = await client.connect()

            # Assert
            assert result is mock_redis
            assert client.client is mock_redis
            mock_redis.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test handling connection failures."""
        # Arrange
        # Set up redis.from_url to raise ConnectionError
        with patch(
            "redis.asyncio.from_url",
            side_effect=redis.ConnectionError("Connection refused"),
        ):
            client = RedisClient()
            client.max_retries = 1  # Set to 1 for faster test

            # Act
            result = await client.connect()

            # Assert
            assert result is None
            assert client.client is None

    @pytest.mark.asyncio
    async def test_get_value(self):
        """Test getting a value from Redis."""
        # Arrange
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "test_value"

        # Create client with mocked Redis connection
        client = RedisClient()
        client.client = mock_redis

        # Act
        result = await client.get("test_key")

        # Assert
        assert result == "test_value"
        mock_redis.get.assert_awaited_once_with("test_key")

    @pytest.mark.asyncio
    async def test_set_value(self):
        """Test setting a value in Redis."""
        # Arrange
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        # Create client with mocked Redis connection
        client = RedisClient()
        client.client = mock_redis

        # Act
        result = await client.set("test_key", "test_value", ttl=60)

        # Assert
        assert result is True
        mock_redis.set.assert_awaited_once_with(
            "test_key", "test_value", ex=60
        )

    @pytest.mark.asyncio
    async def test_delete_key(self):
        """Test deleting a key from Redis."""
        # Arrange
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 1

        # Create client with mocked Redis connection
        client = RedisClient()
        client.client = mock_redis

        # Act
        result = await client.delete("test_key")

        # Assert
        assert result == 1
        mock_redis.delete.assert_awaited_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_object(self):
        """Test getting a serialized object from Redis."""
        # Arrange
        mock_redis = AsyncMock()
        test_data = {
            "id": 1,
            "name": "Test Object",
            "created_at": "2023-01-01T12:00:00",
        }
        mock_redis.get.return_value = json.dumps(test_data)

        # Create client with mocked Redis connection
        client = RedisClient()
        client.client = mock_redis

        # Act
        # Get as dictionary
        dict_result = await client.get_object("test_key")

        # Get as Pydantic model
        model_result = await client.get_object("test_key", TestModel)

        # Assert
        assert dict_result == test_data
        assert isinstance(model_result, TestModel)
        assert model_result.id == 1
        assert model_result.name == "Test Object"
