from unittest.mock import patch

import pytest

from src.api.dependencies import get_api_key
from src.exceptions import AuthenticationError


class TestApiDependencies:
    """Tests for the API dependencies."""

    @pytest.mark.asyncio
    async def test_get_api_key_valid(self):
        """Test successful API key validation."""
        # Arrange
        valid_token = "correct_token"

        # Patch settings to return our test token
        with patch("src.api.dependencies.settings") as mock_settings:
            mock_settings.API_AUTH_TOKEN.get_secret_value.return_value = (
                valid_token
            )

            # Act
            result = await get_api_key(f"Bearer {valid_token}")

            # Assert
            assert result == valid_token

    @pytest.mark.asyncio
    async def test_get_api_key_without_bearer_prefix(self):
        """Test API key validation without 'Bearer' prefix."""
        # Arrange
        valid_token = "correct_token"

        # Patch settings to return our test token
        with patch("src.api.dependencies.settings") as mock_settings:
            mock_settings.API_AUTH_TOKEN.get_secret_value.return_value = (
                valid_token
            )

            # Act
            result = await get_api_key(valid_token)

            # Assert
            assert result == valid_token

    @pytest.mark.asyncio
    async def test_get_api_key_invalid(self):
        """Test invalid API key validation."""
        # Arrange
        valid_token = "correct_token"
        invalid_token = "wrong_token"

        # Patch settings to return our test token
        with patch("src.api.dependencies.settings") as mock_settings:
            mock_settings.API_AUTH_TOKEN.get_secret_value.return_value = (
                valid_token
            )

            # Act & Assert
            with pytest.raises(AuthenticationError) as exc_info:
                await get_api_key(f"Bearer {invalid_token}")

            assert "Invalid API key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_api_key_missing(self):
        """Test missing API key."""
        # Act & Assert
        with pytest.raises(AuthenticationError) as exc_info:
            await get_api_key(None)

        assert "API key is missing" in str(exc_info.value)
