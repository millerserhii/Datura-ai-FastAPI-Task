import json
import logging
from typing import List, Optional, Union, cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.blockchain.client import bittensor_client
from src.blockchain.models import DividendHistory, StakeTransaction
from src.blockchain.repository import BlockchainRepository
from src.blockchain.schemas import (
    StakeOperation,
    TaoDividend,
    TaoDividendsBatch,
)
from src.cache.redis import redis_client
from src.constants import CacheKeys
from src.exceptions import BlockchainError


logger = logging.getLogger(__name__)


class BlockchainService:
    """Service for interacting with blockchain and cache."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize service with an optional database session."""
        self.session = session
        self.repository = BlockchainRepository(session) if session else None

    async def get_tao_dividends(
        self, netuid: Optional[int] = None, hotkey: Optional[str] = None
    ) -> Union[TaoDividend, TaoDividendsBatch]:
        """
        Get Tao dividends with caching.

        Args:
            netuid: Network UID (subnet ID)
            hotkey: Account public key

        Returns:
            TaoDividend or TaoDividendsBatch: Dividend information
        """
        # Generate cache key
        cache_key = CacheKeys.TAO_DIVIDENDS.format(
            netuid=netuid or "all", hotkey=hotkey or "all"
        )

        # Try to get from cache first
        cached_data = await redis_client.get(cache_key)

        if cached_data:
            try:
                data = json.loads(cached_data)

                # Check if it's a single dividend or batch
                if "dividends" in data:
                    dividends_batch = TaoDividendsBatch.model_validate(data)
                    dividends_batch.cached = True
                    return dividends_batch
                else:
                    dividend = TaoDividend.model_validate(data)
                    dividend.cached = True
                    return dividend
            except Exception as e:
                logger.error(f"Failed to parse cached dividend data: {e}")
                # Continue to fetch from blockchain if cache parsing fails

        # If not in cache, fetch from blockchain
        try:
            result = await bittensor_client.get_tao_dividends(netuid, hotkey)

            # Cache the result
            if isinstance(result, list):
                batch = TaoDividendsBatch(dividends=result)
                await redis_client.set_object(cache_key, batch)

                # Record dividends in database if session available
                if self.repository:
                    for dividend in result:
                        await self.repository.record_dividend(dividend)

                return batch
            else:
                await redis_client.set_object(cache_key, result)

                # Record dividend in database if session available
                if self.repository:
                    await self.repository.record_dividend(result)

                return result

        except Exception as e:
            logger.error(f"Failed to get Tao dividends: {e}")
            raise BlockchainError(f"Failed to get Tao dividends: {e}")

    async def stake(
        self,
        amount: float,
        hotkey: Optional[str] = None,
        netuid: Optional[int] = None,
        sentiment_score: Optional[int] = None,
        sentiment_analysis_id: Optional[str] = None,
    ) -> StakeOperation:
        """
        Stake TAO to a hotkey.

        Args:
            amount: Amount to stake
            hotkey: Hotkey to stake to
            netuid: Network UID (subnet ID)
            sentiment_score: Sentiment score that triggered this operation
            sentiment_analysis_id: ID of the sentiment analysis

        Returns:
            StakeOperation: Result of stake operation
        """
        # Use default netuid if not provided
        effective_netuid = (
            netuid if netuid is not None else bittensor_client.default_netuid
        )

        # Perform stake operation
        operation = await bittensor_client.stake(
            amount, hotkey, effective_netuid
        )

        # Record transaction in database if session available
        if self.repository and operation:
            await self.repository.create_stake_transaction(
                operation=operation,
                netuid=effective_netuid,
                sentiment_score=sentiment_score,
                sentiment_analysis_id=sentiment_analysis_id,
            )

        return operation

    async def unstake(
        self,
        amount: float,
        hotkey: Optional[str] = None,
        netuid: Optional[int] = None,
        sentiment_score: Optional[int] = None,
        sentiment_analysis_id: Optional[str] = None,
    ) -> StakeOperation:
        """
        Unstake TAO from a hotkey.

        Args:
            amount: Amount to unstake
            hotkey: Hotkey to unstake from
            netuid: Network UID (subnet ID)
            sentiment_score: Sentiment score that triggered this operation
            sentiment_analysis_id: ID of the sentiment analysis

        Returns:
            StakeOperation: Result of unstake operation
        """
        # Use default netuid if not provided
        effective_netuid = (
            netuid if netuid is not None else bittensor_client.default_netuid
        )

        # Perform unstake operation
        operation = await bittensor_client.unstake(
            amount, hotkey, effective_netuid
        )

        # Record transaction in database if session available
        if self.repository and operation:
            await self.repository.create_stake_transaction(
                operation=operation,
                netuid=effective_netuid,
                sentiment_score=sentiment_score,
                sentiment_analysis_id=sentiment_analysis_id,
            )

        return operation

    async def clear_cache(
        self, netuid: Optional[int] = None, hotkey: Optional[str] = None
    ) -> bool:
        """
        Clear cached dividend data.

        Args:
            netuid: Network UID (subnet ID)
            hotkey: Account public key

        Returns:
            bool: True if cache was cleared
        """
        cache_key = CacheKeys.TAO_DIVIDENDS.format(
            netuid=netuid or "all", hotkey=hotkey or "all"
        )
        deleted = await redis_client.delete(cache_key)
        return deleted > 0

    async def get_stake_transaction_history(
        self,
        netuid: Optional[int] = None,
        hotkey: Optional[str] = None,
        operation_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[StakeTransaction]:
        """
        Get stake transaction history.

        Args:
            netuid: Filter by Network UID
            hotkey: Filter by hotkey
            operation_type: Filter by operation type ("stake" or "unstake")
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[StakeTransaction]: List of stake transactions
        """
        if not self.repository:
            raise BlockchainError("Database session not available")

        return await self.repository.get_stake_transactions(
            netuid=netuid,
            hotkey=hotkey,
            operation_type=operation_type,
            limit=limit,
            offset=offset,
        )

    async def get_dividend_history(
        self,
        netuid: Optional[int] = None,
        hotkey: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DividendHistory]:
        """
        Get dividend history.

        Args:
            netuid: Filter by Network UID
            hotkey: Filter by hotkey
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[DividendHistory]: List of dividend history records
        """
        if not self.repository:
            raise BlockchainError("Database session not available")

        return await self.repository.get_dividend_history(
            netuid=netuid,
            hotkey=hotkey,
            limit=limit,
            offset=offset,
        )


# Factory function to create service with session
async def get_blockchain_service(
    session: Optional[AsyncSession] = None,
) -> BlockchainService:
    """Get blockchain service with optional database session."""
    return BlockchainService(session)


# Initialize global service for use without database operations
blockchain_service = BlockchainService()
