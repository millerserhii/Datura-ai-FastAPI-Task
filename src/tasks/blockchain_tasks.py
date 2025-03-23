import asyncio
import logging
import uuid
from typing import Any, Optional

from celery import shared_task
from requests.exceptions import ConnectionError as RequestsConnectionError

from src.blockchain.service import get_blockchain_service
from src.config import settings
from src.database import async_session
from src.sentiment.service import sentiment_service


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="trigger_sentiment_analysis_and_stake",
    autoretry_for=(RequestsConnectionError,),
    retry_backoff=60,
    max_retries=3,
    queue="sentiment",
)
def trigger_sentiment_analysis_and_stake(
    self, netuid: Optional[int] = None
) -> dict[str, Any]:
    """
    Task to trigger sentiment analysis and stake/unstake operations.

    This task:
    1. Searches for tweets about the subnet using the sentiment service
    2. Analyzes sentiment with Chutes.ai
    3. Stakes or unstakes TAO based on sentiment score

    Args:
        netuid: Network UID (subnet ID)

    Returns:
        dict: Result of the operation
    """
    task_id = self.request.id or str(uuid.uuid4())

    # Use default netuid if not provided
    effective_netuid = (
        netuid if netuid is not None else settings.DEFAULT_NETUID
    )

    logger.info(
        "Starting sentiment analysis and staking for netuid=%s (task_id=%s)",
        effective_netuid,
        task_id,
    )

    # Create a task that will run in an async environment
    async def process_sentiment_and_stake() -> dict[str, Any]:
        try:
            # Get tweets about the subnet
            tweets = await sentiment_service.search_tweets(effective_netuid)

            if not tweets:
                logger.warning(
                    "No tweets found for netuid=%s", effective_netuid
                )
                return {
                    "task_id": task_id,
                    "netuid": effective_netuid,
                    "status": "completed",
                    "message": "No tweets found for sentiment analysis",
                    "sentiment_score": 0,
                    "operation": "none",
                    "amount": 0,
                    "success": True,
                }

            # Analyze sentiment
            sentiment_result = await sentiment_service.analyze_sentiment(
                tweets, effective_netuid
            )
            sentiment_id = uuid.uuid4()

            # Skip staking if sentiment is neutral
            if sentiment_result.operation_type == "none":
                logger.info(
                    "Neutral sentiment (%s) for netuid=%s, skipping stake/unstake",
                    sentiment_result.score,
                    effective_netuid,
                )
                return {
                    "task_id": task_id,
                    "netuid": effective_netuid,
                    "status": "completed",
                    "message": "Neutral sentiment, no action taken",
                    "sentiment_score": sentiment_result.score,
                    "operation": "none",
                    "amount": 0,
                    "success": True,
                }

            # Get blockchain service with session
            async with async_session() as session:
                service = await get_blockchain_service(session)

                # Perform stake or unstake based on sentiment
                if sentiment_result.operation_type == "stake":
                    logger.info(
                        "Positive sentiment (%s) for netuid=%s, staking %s TAO",
                        sentiment_result.score,
                        effective_netuid,
                        sentiment_result.stake_amount,
                    )

                    # Stake TAO
                    operation = await service.stake(
                        amount=sentiment_result.stake_amount,
                        netuid=effective_netuid,
                        sentiment_score=sentiment_result.score,
                        sentiment_analysis_id=sentiment_id,
                    )

                    return {
                        "task_id": task_id,
                        "netuid": effective_netuid,
                        "status": "completed",
                        "message": (
                            "Successfully staked"
                            if operation.success
                            else f"Failed to stake: {operation.error}"
                        ),
                        "sentiment_score": sentiment_result.score,
                        "operation": "stake",
                        "amount": sentiment_result.stake_amount,
                        "success": operation.success,
                        "tx_hash": operation.tx_hash,
                    }

                else:  # unstake
                    logger.info(
                        "Negative sentiment (%s) for netuid=%s, unstaking %s TAO",
                        sentiment_result.score,
                        effective_netuid,
                        sentiment_result.stake_amount,
                    )

                    # Unstake TAO
                    operation = await service.unstake(
                        amount=sentiment_result.stake_amount,
                        netuid=effective_netuid,
                        sentiment_score=sentiment_result.score,
                        sentiment_analysis_id=sentiment_id,
                    )

                    return {
                        "task_id": task_id,
                        "netuid": effective_netuid,
                        "status": "completed",
                        "message": (
                            "Successfully unstaked"
                            if operation.success
                            else f"Failed to unstake: {operation.error}"
                        ),
                        "sentiment_score": sentiment_result.score,
                        "operation": "unstake",
                        "amount": sentiment_result.stake_amount,
                        "success": operation.success,
                        "tx_hash": operation.tx_hash,
                    }
        except Exception as e:
            logger.exception("Error in sentiment analysis process: %s", e)
            return {
                "task_id": task_id,
                "netuid": effective_netuid,
                "status": "failed",
                "message": f"Error in sentiment analysis: {str(e)}",
                "success": False,
            }

    # Run the async task in an event loop
    try:
        # Create a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Run the async task
        result = loop.run_until_complete(process_sentiment_and_stake())
        loop.close()

        return result

    except Exception as e:
        logger.exception(
            "Error in sentiment analysis and staking task for netuid=%s: %s",
            effective_netuid,
            e,
        )

        return {
            "task_id": task_id,
            "netuid": effective_netuid,
            "status": "failed",
            "message": f"Error: {str(e)}",
            "success": False,
        }
