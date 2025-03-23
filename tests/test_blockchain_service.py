import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.blockchain.schemas import StakeOperation, TaoDividend
from src.blockchain.service import BlockchainService
from src.constants import CacheKeys


class TestBlockchainService:
    """Tests for the BlockchainService."""

    @pytest.mark.asyncio
    async def test_get_tao_dividends_from_blockchain(
        self,
        test_session,
        mock_bittensor_client,
        mock_redis_client,
        mock_tao_dividend,
    ):
        """Test getting Tao dividends from blockchain when not in cache."""
        # Arrange
        # Mock the repository to avoid using the session
        mock_repository = MagicMock()
        mock_repository.record_dividend = AsyncMock()

        service = BlockchainService(test_session)
        service.repository = mock_repository

        netuid = 18
        hotkey = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"

        # Mock Redis cache miss
        mock_redis_client.get.return_value = None

        # Mock bittensor client response
        mock_bittensor_client.get_tao_dividends.return_value = (
            mock_tao_dividend
        )

        # Act
        with patch("src.blockchain.service.redis_client", mock_redis_client):
            with patch(
                "src.blockchain.service.bittensor_client",
                mock_bittensor_client,
            ):
                result = await service.get_tao_dividends(netuid, hotkey)

        # Assert
        assert isinstance(result, TaoDividend)
        assert result.netuid == netuid
        assert result.hotkey == hotkey
        assert result.cached is False

        # Verify mocks were called correctly
        cache_key = CacheKeys.TAO_DIVIDENDS.format(
            netuid=netuid, hotkey=hotkey
        )
        mock_redis_client.get.assert_called_once_with(cache_key)
        mock_bittensor_client.get_tao_dividends.assert_called_once_with(
            netuid, hotkey
        )
        mock_redis_client.set_object.assert_called_once()
        mock_repository.record_dividend.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tao_dividends_from_cache(
        self,
        test_session,
        mock_bittensor_client,
        mock_redis_client,
        mock_tao_dividend,
    ):
        """Test getting Tao dividends from cache."""
        # Arrange
        service = BlockchainService(test_session)
        netuid = 18
        hotkey = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"

        # Mock Redis cache hit
        cached_dividend = mock_tao_dividend.model_dump()
        mock_redis_client.get.return_value = json.dumps(cached_dividend)

        # Act
        with patch("src.blockchain.service.redis_client", mock_redis_client):
            with patch(
                "src.blockchain.service.bittensor_client",
                mock_bittensor_client,
            ):
                result = await service.get_tao_dividends(netuid, hotkey)

        # Assert
        assert isinstance(result, TaoDividend)
        assert result.netuid == netuid
        assert result.hotkey == hotkey
        assert result.cached is True

        # Verify bittensor client was not called
        mock_bittensor_client.get_tao_dividends.assert_not_called()

    @pytest.mark.asyncio
    async def test_stake_success(
        self, test_session, mock_bittensor_client, mock_stake_operation
    ):
        """Test successful stake operation."""
        # Arrange
        # Mock the repository to avoid using the session
        mock_repository = MagicMock()
        mock_repository.create_stake_transaction = AsyncMock()

        service = BlockchainService(test_session)
        service.repository = mock_repository

        amount = 1.5
        hotkey = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"
        netuid = 18

        # Mock bittensor client stake response
        mock_bittensor_client.stake.return_value = mock_stake_operation

        # Act
        with patch(
            "src.blockchain.service.bittensor_client", mock_bittensor_client
        ):
            result = await service.stake(amount, hotkey, netuid)

        # Assert
        assert isinstance(result, StakeOperation)
        assert result.hotkey == hotkey
        assert result.amount == amount
        assert result.operation_type == "stake"
        assert result.success is True

        # Verify mock was called correctly
        mock_bittensor_client.stake.assert_called_once_with(
            amount, hotkey, netuid
        )
        mock_repository.create_stake_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_unstake_success(self, test_session, mock_bittensor_client):
        """Test successful unstake operation."""
        # Arrange
        # Mock the repository to avoid using the session
        mock_repository = MagicMock()
        mock_repository.create_stake_transaction = AsyncMock()

        service = BlockchainService(test_session)
        service.repository = mock_repository

        amount = 1.5
        hotkey = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"
        netuid = 18

        # Create unstake operation response
        unstake_op = StakeOperation(
            hotkey=hotkey,
            amount=amount,
            operation_type="unstake",
            tx_hash="0x1234567890abcdef",
            success=True,
        )

        # Mock bittensor client unstake response
        mock_bittensor_client.unstake.return_value = unstake_op

        # Act
        with patch(
            "src.blockchain.service.bittensor_client", mock_bittensor_client
        ):
            result = await service.unstake(amount, hotkey, netuid)

        # Assert
        assert isinstance(result, StakeOperation)
        assert result.hotkey == hotkey
        assert result.amount == amount
        assert result.operation_type == "unstake"
        assert result.success is True

        # Verify mock was called correctly
        mock_bittensor_client.unstake.assert_called_once_with(
            amount, hotkey, netuid
        )
        mock_repository.create_stake_transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_cache(self, test_session, mock_redis_client):
        """Test clearing cache for a specific netuid and hotkey."""
        # Arrange
        service = BlockchainService(test_session)
        netuid = 18
        hotkey = "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v"

        # Mock Redis delete response
        mock_redis_client.delete.return_value = 1

        # Act
        with patch("src.blockchain.service.redis_client", mock_redis_client):
            result = await service.clear_cache(netuid, hotkey)

        # Assert
        assert result is True

        # Verify mock was called correctly
        cache_key = CacheKeys.TAO_DIVIDENDS.format(
            netuid=netuid, hotkey=hotkey
        )
        mock_redis_client.delete.assert_called_once_with(cache_key)
