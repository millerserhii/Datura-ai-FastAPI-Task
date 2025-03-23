import logging
import uuid
from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.sentiment.models import SentimentAnalysis
from src.sentiment.schemas import SentimentResult


logger = logging.getLogger(__name__)


class SentimentAnalysisRepository:
    """Repository for sentiment analysis database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_sentiment_analysis(
        self,
        result: SentimentResult,
        tweets_text: Optional[str] = None,
    ) -> SentimentAnalysis:
        """
        Create a new sentiment analysis record.

        Args:
            result: Sentiment analysis result
            tweets_text: Optional concatenated tweets text for reference

        Returns:
            SentimentAnalysis: Created analysis record
        """
        analysis = SentimentAnalysis(
            netuid=result.netuid,
            score=result.score,
            tweets_count=result.tweets_count,
            operation_type=result.operation_type,
            stake_amount=result.stake_amount,
            tweets_text=tweets_text,
        )

        self.session.add(analysis)
        await self.session.commit()
        await self.session.refresh(analysis)

        logger.info(
            "Created sentiment analysis record for netuid=%s, score=%s, operation=%s",
            analysis.netuid,
            analysis.score,
            analysis.operation_type,
        )

        return analysis

    async def get_sentiment_analyses(
        self,
        netuid: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SentimentAnalysis]:
        """
        Get sentiment analysis records with optional filters.

        Args:
            netuid: Filter by Network UID
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List[SentimentAnalysis]: List of sentiment analysis records
        """
        query = select(SentimentAnalysis).order_by(
            desc(SentimentAnalysis.timestamp)  # type: ignore[arg-type]
        )

        if netuid is not None:
            query = query.where(
                SentimentAnalysis.netuid == netuid  # type: ignore[arg-type]
            )

        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_sentiment_analysis_by_id(
        self, analysis_id: uuid.UUID
    ) -> Optional[SentimentAnalysis]:
        """
        Get a specific sentiment analysis record by ID.

        Args:
            analysis_id: Sentiment analysis ID

        Returns:
            Optional[SentimentAnalysis]: The analysis record if found, None otherwise
        """
        query = select(SentimentAnalysis).where(
            SentimentAnalysis.id == analysis_id  # type: ignore[arg-type]
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_latest_sentiment_analysis(
        self, netuid: int
    ) -> Optional[SentimentAnalysis]:
        """
        Get the most recent sentiment analysis for a specific subnet.

        Args:
            netuid: Network UID (subnet ID)

        Returns:
            Optional[SentimentAnalysis]: The latest analysis record if found, None otherwise
        """
        query = (
            select(SentimentAnalysis)
            .where(SentimentAnalysis.netuid == netuid)  # type: ignore[arg-type]
            .order_by(desc(SentimentAnalysis.timestamp))  # type: ignore[arg-type]
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
