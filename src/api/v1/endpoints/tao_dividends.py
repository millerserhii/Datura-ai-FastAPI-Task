from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_api_key
from src.blockchain.schemas import TaoDividend, TaoDividendsBatch
from src.blockchain.service import get_blockchain_service
from src.database import get_session
from src.exceptions import BlockchainError
from src.tasks.blockchain_tasks import trigger_sentiment_analysis_and_stake

router = APIRouter()


@router.get(
    "",
    response_model=Union[TaoDividend, TaoDividendsBatch],
    status_code=status.HTTP_200_OK,
    summary="Get Tao dividends",
    description=(
        "Get Tao dividends for the specified netuid and hotkey. "
        "If netuid is omitted, returns data for all netuids. "
        "If hotkey is omitted, returns data for all "
        "hotkeys on the specified netuid. "
        "When trade=True, will trigger sentiment "
        "analysis and stake/unstake operations."
    ),
)
async def get_tao_dividends(
    netuid: Optional[int] = Query(None, description="Network UID (subnet ID)"),
    hotkey: Optional[str] = Query(None, description="Account public key"),
    trade: bool = Query(
        False,
        description="Trigger sentiment analysis and stake/unstake operations",
    ),
    _: str = Depends(get_api_key),
    session: AsyncSession = Depends(get_session),
) -> Union[TaoDividend, TaoDividendsBatch]:
    """
    Get Tao dividends for the specified netuid and hotkey.

    Args:
        netuid: Network UID (subnet ID)
        hotkey: Account public key
        trade: Trigger sentiment analysis and stake/unstake operations
        _: API key (from dependency)
        session: Database session

    Returns:
        TaoDividend or TaoDividendsBatch: Dividend information
    """
    try:
        # Get blockchain service with database session
        service = await get_blockchain_service(session)

        # Get Tao dividends
        result = await service.get_tao_dividends(netuid, hotkey)

        # If trade is enabled, trigger sentiment
        # analysis and stake/unstake operations
        if trade:
            # Use default values if not provided
            trigger_netuid = netuid if netuid is not None else None

            # Trigger sentiment analysis and stake/unstake as a background task
            trigger_sentiment_analysis_and_stake.delay(trigger_netuid)

            # Mark stake_tx_triggered as True
            if isinstance(result, TaoDividendsBatch):
                result.stake_tx_triggered = True
                for dividend in result.dividends:
                    dividend.stake_tx_triggered = True
            else:
                result.stake_tx_triggered = True

        return result
    except BlockchainError as e:
        # Re-raise as HTTPException with appropriate status code
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        ) from e
