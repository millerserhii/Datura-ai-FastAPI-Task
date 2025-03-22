import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class StakeTransaction(SQLModel, table=True):
    """Model for stake/unstake transactions."""

    __tablename__ = "stake_transactions"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    operation_type: str = Field(index=True)  # "stake" or "unstake"
    netuid: int = Field(index=True)
    hotkey: str = Field(index=True)
    amount: float
    tx_hash: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="pending")  # "successful", "failed", "pending"
    error: Optional[str] = Field(default=None)
    sentiment_score: Optional[int] = Field(default=None)


class DividendHistory(SQLModel, table=True):
    """Model for tracking dividend history."""

    __tablename__ = "dividend_history"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    netuid: int = Field(index=True)
    hotkey: str = Field(index=True)
    dividend_value: int
    source: str = Field(default="blockchain")  # "cache" or "blockchain"
