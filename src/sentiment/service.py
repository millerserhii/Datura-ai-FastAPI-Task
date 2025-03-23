import logging

import aiohttp
from pydantic import BaseModel

from src.exceptions import ExternalAPIError
from src.sentiment.schemas import SentimentResult


logger = logging.getLogger(__name__)


class TwitterUser(BaseModel):
    """Twitter user model."""

    id: str
    username: str
    name: str
    followers_count: int = 0
    verified: bool = False
    is_blue_verified: bool = False


class Tweet(BaseModel):
    """Twitter tweet model with engagement metrics."""

    id: str
    text: str
    url: str
    created_at: str

    # User information
    user: TwitterUser

    # Engagement metrics
    reply_count: int = 0
    retweet_count: int = 0
    like_count: int = 0
    quote_count: int = 0
    bookmark_count: int = 0

    # Additional metadata
    is_quote_tweet: bool = False
    is_retweet: bool = False
    lang: str = "en"


class SentimentAnalysisService:
    """Service for Twitter sentiment analysis."""

    def __init__(self, datura_api_key: str, chutes_api_key: str):
        """Initialize service."""
        self.datura_api_key = datura_api_key
        self.chutes_api_key = chutes_api_key
        self.datura_base_url = "https://apis.datura.ai"
        self.chutes_base_url = "https://llm.chutes.ai/v1/chat"

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

        logger.info("Searching tweets about subnet %s", netuid)

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": self.datura_api_key,
                "Content-Type": "application/json",
            }

            payload = {
                "query": query,
                "blue_verified": False,
                "lang": "en",
                "sort": "Latest",
                "count": max_results,
            }

            try:
                async with session.post(
                    f"{self.datura_base_url}/twitter",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise ExternalAPIError(
                            f"Failed to search tweets: {response.status} - {text}"
                        )

                    data = await response.json()

                    tweets = []
                    for tweet_data in data:
                        try:
                            # Extract user data from the response
                            user_data = tweet_data.get("user", {})
                            user = TwitterUser(
                                id=user_data.get("id", ""),
                                username=user_data.get("username", ""),
                                name=user_data.get("name", ""),
                                followers_count=user_data.get(
                                    "followers_count", 0
                                ),
                                verified=user_data.get("verified", False),
                                is_blue_verified=user_data.get(
                                    "is_blue_verified", False
                                ),
                            )

                            # Create Tweet object
                            tweet = Tweet(
                                id=tweet_data.get("id", ""),
                                text=tweet_data.get("text", ""),
                                url=tweet_data.get("url", ""),
                                created_at=tweet_data.get("created_at", ""),
                                user=user,
                                reply_count=tweet_data.get("reply_count", 0),
                                retweet_count=tweet_data.get(
                                    "retweet_count", 0
                                ),
                                like_count=tweet_data.get("like_count", 0),
                                quote_count=tweet_data.get("quote_count", 0),
                                bookmark_count=tweet_data.get(
                                    "bookmark_count", 0
                                ),
                                is_quote_tweet=tweet_data.get(
                                    "is_quote_tweet", False
                                ),
                                is_retweet=tweet_data.get("is_retweet", False),
                                lang=tweet_data.get("lang", "en"),
                            )
                            tweets.append(tweet)
                        except Exception as e:
                            logger.error(f"Error processing tweet: {e}")
                            continue

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

        # Format tweet information including engagement metrics
        tweet_texts = []
        for tweet in tweets:
            engagement_info = (
                f"[Engagement: {tweet.like_count} likes, "
                f"{tweet.retweet_count} retweets, "
                f"{tweet.reply_count} replies, "
                f"{tweet.quote_count} quotes, "
                f"{tweet.bookmark_count} bookmarks]"
            )

            user_info = f"@{tweet.user.username}"
            if tweet.user.verified or tweet.user.is_blue_verified:
                user_info += " (verified)"

            followers_info = f"{tweet.user.followers_count} followers"

            tweet_info = (
                f"Tweet by {user_info} ({followers_info}):\n"
                f"{tweet.text}\n"
                f"{engagement_info}\n"
            )

            tweet_texts.append(tweet_info)

        combined_text = "\n\n".join(tweet_texts)

        # Chutes.ai prompt for sentiment analysis
        system_message = f"""
            Analyze the sentiment of these tweets about Bittensor subnet 18.
            Rate the overall sentiment on a scale from -100
            (extremely negative)
            to +100 (extremely positive). Consider both the content of the
            tweets and their engagement metrics. Tweets with higher engagement
            (likes, retweets) should be weighted more heavily.
            IMPORTANT: Your response must be ONLY a single integer
            number between -100 and +100, with no explanations, calculations,
            or additional text of any kind. Just the number.
            For example: 42 or -87
        """

        # Call Chutes.ai API
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.chutes_api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": "unsloth/Llama-3.2-3B-Instruct",
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": combined_text},
                ],
                "max_tokens": 10,
            }

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
                    logger.info("Chutes API response: %s", data)
                    completion = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "0")
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
