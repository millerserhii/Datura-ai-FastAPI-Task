import logging
import uuid
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.blockchain.models import DividendHistory, StakeTransaction
from src.blockchain.schemas import StakeOperation, TaoDividend


logger = logging.getLogger(__name__)


class BlockchainRepository:
    """Repository for blockchain database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_stake_transaction(
        self,
        operation: StakeOperation,
        netuid: int,
        sentiment_score: Optional[int] = None,
        sentiment_analysis_id: Optional[uuid.UUID] = None,
    ) -> StakeTransaction:
        """
        Create a new stake transaction record.

        Args:
            operation: Stake operation details
            netuid: Network UID (subnet ID)
            sentiment_score: Sentiment score that triggered the operation
            sentiment_analysis_id: ID of the related sentiment analysis

        Returns:
            StakeTransaction: Created transaction record
        """
        transaction = StakeTransaction(
            operation_type=operation.operation_type,
            netuid=netuid,
            hotkey=operation.hotkey,
            amount=operation.amount,
            tx_hash=operation.tx_hash,
            status="successful" if operation.success else "failed",
            error=operation.error,
            sentiment_score=sentiment_score,
            sentiment_analysis_id=sentiment_analysis_id,
        )

        self.session.add(transaction)
        await self.session.commit()
        await self.session.refresh(transaction)

        logger.info(
            "Created %s transaction record for hotkey=%s, amount=%s",
            transaction.operation_type,
            transaction.hotkey,
            transaction.amount,
        )

        return transaction

    async def get_stake_transactions(
        self,
        netuid: Optional[int] = None,
        hotkey: Optional[str] = None,
        operation_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StakeTransaction]:
        """
        Get stake transactions with optional filters.

        Args:
            netuid: Filter by Network UID
            hotkey: Filter by hotkey
            operation_type: Filter by operation type ("stake" or "unstake")
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[StakeTransaction]: List of stake transactions
        """
        query = select(StakeTransaction).order_by(
            desc(StakeTransaction.timestamp)  # type: ignore[arg-type]
        )

        if netuid is not None:
            query = query.where(
                StakeTransaction.netuid == netuid  # type: ignore[arg-type]
            )

        if hotkey:
            query = query.where(
                StakeTransaction.hotkey == hotkey  # type: ignore[arg-type]
            )

        if operation_type:
            query = query.where(
                StakeTransaction.operation_type == operation_type  # type: ignore[arg-type] # noqa: E501 # pylint: disable=line-too-long
            )

        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def record_dividend(
        self, dividend: TaoDividend, source: str = "blockchain"
    ) -> DividendHistory:
        """
        Record a dividend value in history.

        Args:
            dividend: Dividend data
            source: Source of the data ("blockchain" or "cache")

        Returns:
            DividendHistory: Created history record
        """
        history = DividendHistory(
            netuid=dividend.netuid,
            hotkey=dividend.hotkey,
            dividend_value=dividend.dividend,
            source=source,
        )

        self.session.add(history)
        await self.session.commit()
        await self.session.refresh(history)

        logger.debug(
            "Recorded dividend history for netuid=%s, hotkey=%s, value=%s",
            history.netuid,
            history.hotkey,
            history.dividend_value,
        )

        return history

    async def get_dividend_history(
        self,
        netuid: Optional[int] = None,
        hotkey: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DividendHistory]:
        """
        Get dividend history with optional filters.

        Args:
            netuid: Filter by Network UID
            hotkey: Filter by hotkey
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[DividendHistory]: List of dividend history records
        """
        query = select(DividendHistory).order_by(
            desc(DividendHistory.timestamp)  # type: ignore[arg-type]
        )

        if netuid is not None:
            query = query.where(
                DividendHistory.netuid == netuid  # type: ignore[arg-type]
            )

        if hotkey:
            query = query.where(
                DividendHistory.hotkey == hotkey  # type: ignore[arg-type]
            )

        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())
