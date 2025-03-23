import logging
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from kombu.exceptions import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_api_key
from src.blockchain.schemas import TaoDividend, TaoDividendsBatch
from src.blockchain.service import get_blockchain_service
from src.config import settings
from src.database import get_session
from src.exceptions import BlockchainError
from src.tasks.blockchain_tasks import trigger_sentiment_analysis_and_stake


logger = logging.getLogger(__name__)

router = APIRouter()

NETUID_QUERY = Query(None, description="Network UID (subnet ID)")
HOTKEY_QUERY = Query(None, description="Account public key")
TRADE_QUERY = Query(
    False,
    description="Trigger sentiment analysis and stake/unstake operations",
)


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
    netuid: int = NETUID_QUERY,
    hotkey: str = HOTKEY_QUERY,
    trade: bool = TRADE_QUERY,
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

        # Apply default values if not provided
        effective_netuid = netuid if netuid is not None else None
        effective_hotkey = hotkey if hotkey is not None else None

        # Get Tao dividends
        result = await service.get_tao_dividends(
            effective_netuid, effective_hotkey
        )

        # If trade is enabled, trigger sentiment analysis and stake/unstake operations
        if trade:
            # Use default netuid if not provided
            trigger_netuid = (
                effective_netuid
                if effective_netuid is not None
                else settings.DEFAULT_NETUID
            )

            try:
                # Trigger sentiment analysis and stake/unstake as a background task
                task = trigger_sentiment_analysis_and_stake.delay(
                    trigger_netuid
                )
                logger.info(
                    f"Triggered sentiment analysis task (ID: {task.id}) for netuid={trigger_netuid}"
                )

                # Mark stake_tx_triggered as True
                if isinstance(result, TaoDividendsBatch):
                    result.stake_tx_triggered = True
                    for dividend in result.dividends:
                        dividend.stake_tx_triggered = True
                else:
                    result.stake_tx_triggered = True

            except (OperationalError, ConnectionError) as e:
                # Handle connection errors gracefully
                logger.error(f"Failed to connect to Celery broker: {str(e)}")
                # Still return data even if background task fails
                if isinstance(result, TaoDividendsBatch):
                    result.stake_tx_triggered = False
                    for dividend in result.dividends:
                        dividend.stake_tx_triggered = False
                else:
                    result.stake_tx_triggered = False

            except Exception as e:
                # Handle other task-related errors
                logger.error(
                    f"Error triggering sentiment analysis task: {str(e)}"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error triggering sentiment analysis task: {str(e)}",
                ) from e

        return result

    except BlockchainError as e:
        # Re-raise as HTTPException with appropriate status code
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    except Exception as e:
        # Handle unexpected errors
        logger.exception(f"Unexpected error in get_tao_dividends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        ) from e
