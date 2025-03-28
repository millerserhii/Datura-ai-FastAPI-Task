import logging
from asyncio import Semaphore
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
MAX_CONCURRENT_SENTIMENT_TASKS = 20
sentiment_task_semaphore = Semaphore(MAX_CONCURRENT_SENTIMENT_TASKS)


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

        # Ensure we have a valid result - if we don't, create a default
        if result is None:
            logger.warning(
                "Blockchain service returned None, creating default response"
            )
            if effective_hotkey is not None:
                # Single hotkey query, return a single dividend
                result = TaoDividend(
                    netuid=(
                        effective_netuid
                        if effective_netuid is not None
                        else settings.DEFAULT_NETUID
                    ),
                    hotkey=effective_hotkey,
                    dividend=0,
                    cached=False,
                )
            else:
                # Multiple hotkeys query, return an empty batch
                result = TaoDividendsBatch(
                    dividends=[],
                    cached=False,
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
                # Check if we can acquire the semaphore
                if sentiment_task_semaphore.locked():
                    # Skip the sentiment analysis if we're at
                    # capacity but still return data
                    logger.warning(
                        "Sentiment analysis task queue at capacity. "
                        "Skipping analysis for this request."
                    )

                    # Mark stake_tx_triggered as False
                    if isinstance(result, TaoDividendsBatch):
                        result.stake_tx_triggered = False
                        for dividend in result.dividends:
                            dividend.stake_tx_triggered = False
                    else:
                        result.stake_tx_triggered = False
                else:
                    # We can proceed with sentiment analysis
                    async with sentiment_task_semaphore:
                        # Trigger sentiment analysis and stake/unstake
                        # as a background task
                        datura_api_key = (
                            settings.DATURA_API_KEY.get_secret_value()
                        )
                        chutes_api_key = (
                            settings.CHUTES_API_KEY.get_secret_value()
                        )
                        task = trigger_sentiment_analysis_and_stake.delay(
                            datura_api_key=datura_api_key,
                            chutes_api_key=chutes_api_key,
                            netuid=trigger_netuid,
                        )
                        logger.info(
                            f"Triggered sentiment analysis task (ID: {task.id}) "
                            f"for netuid={trigger_netuid}"
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

        # Ensure we return a valid result
        if result is None:
            # This should never happen due to our earlier check, but just in case
            logger.error(
                "Result is still None before returning, creating emergency default"
            )
            if effective_hotkey is not None:
                return TaoDividend(
                    netuid=(
                        effective_netuid
                        if effective_netuid is not None
                        else settings.DEFAULT_NETUID
                    ),
                    hotkey=effective_hotkey,
                    dividend=0,
                    cached=False,
                    stake_tx_triggered=False,
                )
            else:
                return TaoDividendsBatch(
                    dividends=[],
                    cached=False,
                    stake_tx_triggered=False,
                )

        return result

    except BlockchainError as e:
        # Re-raise as HTTPException with appropriate status code
        logger.error(f"BlockchainError: {str(e)}")

        # Create a default response instead of raising an exception
        if hotkey is not None:
            return TaoDividend(
                netuid=(
                    netuid if netuid is not None else settings.DEFAULT_NETUID
                ),
                hotkey=hotkey,
                dividend=0,
                cached=False,
                stake_tx_triggered=False,
            )
        else:
            return TaoDividendsBatch(
                dividends=[],
                cached=False,
                stake_tx_triggered=False,
            )
    except Exception as e:
        # Handle unexpected errors
        logger.exception(f"Unexpected error in get_tao_dividends: {str(e)}")

        # Create a default response instead of raising an exception
        if hotkey is not None:
            return TaoDividend(
                netuid=(
                    netuid if netuid is not None else settings.DEFAULT_NETUID
                ),
                hotkey=hotkey,
                dividend=0,
                cached=False,
                stake_tx_triggered=False,
            )
        else:
            return TaoDividendsBatch(
                dividends=[],
                cached=False,
                stake_tx_triggered=False,
            )
