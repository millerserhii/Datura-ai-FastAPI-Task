import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class SentimentAnalysis(SQLModel, table=True):
    """Model for sentiment analysis records."""

    __tablename__ = "sentiment_analyses"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    netuid: int = Field(index=True)
    score: int  # -100 to +100
    tweets_count: int
    operation_type: str  # "stake", "unstake", or "none"
    stake_amount: float
    tweets_text: Optional[str] = Field(default=None)
