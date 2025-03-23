from typing import Optional

from pydantic import BaseModel, Field


class TaoDividend(BaseModel):
    """Tao dividend model."""

    netuid: int
    hotkey: str
    dividend: float
    cached: bool = False
    stake_tx_triggered: bool = False
    tx_hash: Optional[str] = None


class TaoDividendsBatch(BaseModel):
    """Multiple Tao dividends model."""

    dividends: list[TaoDividend] = Field(default_factory=list)
    cached: bool = False
    stake_tx_triggered: bool = False

    @property
    def total_dividend(self) -> float:
        """Calculate total dividend."""
        return sum(dividend.dividend for dividend in self.dividends)


class StakeOperation(BaseModel):
    """Stake operation model."""

    hotkey: str
    amount: float
    operation_type: str  # "stake" or "unstake"
    tx_hash: Optional[str] = None
    success: bool = False
    error: Optional[str] = None
