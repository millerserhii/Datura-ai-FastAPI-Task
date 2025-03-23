import logging

import aiohttp
from pydantic import BaseModel, Field

from src.blockchain.schemas import SentimentResult
from src.cache.redis import redis_client
from src.config import settings
from src.constants import CacheKeys
from src.exceptions import ExternalAPIError


logger = logging.getLogger(__name__)


class Tweet(BaseModel):
    """Twitter tweet model."""

    id: str
    text: str
    created_at: str
    author_username: str = Field(alias="username")
    author_id: str = Field(alias="author_id")

    class Config:
        populate_by_name = True


class SentimentAnalysisService:
    """Service for Twitter sentiment analysis."""

    def __init__(self):
        """Initialize service."""
        self.datura_api_key = settings.DATURA_API_KEY.get_secret_value()
        self.chutes_api_key = settings.CHUTES_API_KEY.get_secret_value()
        self.datura_base_url = "https://api.datura.ai/api/v1"
        self.chutes_base_url = "https://api.chutes.ai/api/v1"

    async def search_tweets(
        self, netuid: int, max_results: int = 10
    ) -> list[Tweet]:
        """
        Search for tweets about the specified subnet.

        Args:
            netuid: Network UID (subnet ID)
            max_results: Maximum number of tweets to return

        Returns:
            List[Tweet]: List of tweets
        """
        query = f"Bittensor netuid {netuid}"

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.datura_api_key}",
                "Content-Type": "application/json",
            }

            params = {
                "query": query,
                "max_results": max_results,
                "sort_order": "recency",
            }

            try:
                async with session.get(
                    f"{self.datura_base_url}/twitter/search",
                    headers=headers,
                    params=params,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise ExternalAPIError(
                            f"Failed to search tweets: {response.status} - {text}"
                        )

                    data = await response.json()
                    tweets = [
                        Tweet.model_validate(tweet)
                        for tweet in data.get("data", [])
                    ]

                    logger.info(
                        "Found %s tweets about subnet %s", len(tweets), netuid
                    )

                    return tweets

            except aiohttp.ClientError as e:
                logger.error("Datura API error: %s", e)
                raise ExternalAPIError(f"Datura API error: {e}") from e

    async def analyze_sentiment(
        self, tweets: list[Tweet], netuid: int
    ) -> SentimentResult:
        """
        Analyze sentiment of tweets using Chutes.ai.

        Args:
            tweets: List of tweets to analyze
            netuid: Network UID (subnet ID)

        Returns:
            SentimentResult: Sentiment analysis result
        """
        if not tweets:
            # Default to neutral sentiment if no tweets found
            return SentimentResult(
                netuid=netuid,
                score=0,
                tweets_count=0,
                operation_type="none",
                stake_amount=0,
            )

        # Try to get from cache first
        cache_key = CacheKeys.SENTIMENT_ANALYSIS.format(netuid=netuid)
        cached_result = await redis_client.get_object(
            cache_key, SentimentResult
        )

        if cached_result:
            logger.info(
                "Using cached sentiment analysis for subnet %s: %s",
                netuid,
                cached_result.score,
            )
            return cached_result

        # Combine tweet texts for analysis
        combined_text = "\n\n".join([tweet.text for tweet in tweets])

        # Chutes.ai prompt for sentiment analysis
        prompt = f"""
        Analyze the sentiment of these tweets about Bittensor subnet {netuid}.
        Rate the overall sentiment on a scale from -100 (extremely negative)
        to +100 (extremely positive).

        Tweets:
        {combined_text}

        Return ONLY a number between -100 and +100 representing the sentiment score.
        """

        # Call Chutes.ai API
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.chutes_api_key}",
                "Content-Type": "application/json",
            }

            payload = {"model": "llama3", "prompt": prompt, "max_tokens": 10}

            try:
                async with session.post(
                    f"{self.chutes_base_url}/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise ExternalAPIError(
                            f"Failed to analyze sentiment: {response.status} - {text}"
                        )

                    data = await response.json()
                    completion = (
                        data.get("choices", [{}])[0].get("text", "0").strip()
                    )

                    # Extract the sentiment score from the completion
                    try:
                        score = int(completion)
                        # Ensure the score is within range
                        score = max(-100, min(100, score))
                    except ValueError:
                        logger.warning(
                            "Failed to parse sentiment score: %s", completion
                        )
                        score = 0

                    # Determine operation type and amount based on sentiment
                    operation_type = (
                        "stake"
                        if score > 0
                        else "unstake" if score < 0 else "none"
                    )
                    stake_amount = abs(score) * 0.01 if score != 0 else 0

                    # Create result
                    result = SentimentResult(
                        netuid=netuid,
                        score=score,
                        tweets_count=len(tweets),
                        operation_type=operation_type,
                        stake_amount=stake_amount,
                    )

                    # Cache the result
                    await redis_client.set_object(
                        cache_key, result, ttl=60 * 30
                    )  # 30 minutes

                    logger.info(
                        "Sentiment analysis for subnet %s: %s (%s)",
                        netuid,
                        score,
                        operation_type,
                    )

                    return result

            except aiohttp.ClientError as e:
                logger.error("Chutes API error: %s", e)
                raise ExternalAPIError(f"Chutes API error: {e}") from e


# Initialize global service
sentiment_service = SentimentAnalysisService()
