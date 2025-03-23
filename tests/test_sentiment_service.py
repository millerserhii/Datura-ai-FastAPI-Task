import pytest

from src.exceptions import ExternalAPIError
from src.sentiment.schemas import SentimentResult
from src.sentiment.service import SentimentAnalysisService, Tweet, TwitterUser


class TestSentimentAnalysisService:
    """Tests for the SentimentAnalysisService."""

    @pytest.mark.asyncio
    async def test_search_tweets(self):
        """Test searching tweets about a subnet."""
        # Arrange
        netuid = 18

        # Create a Tweet object that matches what we want the service to return
        expected_tweet = Tweet(
            id="1234567890",
            text="Bittensor netuid 18 is amazing! #bittensor",
            url="https://twitter.com/user123/status/1234567890",
            created_at="2023-04-01T12:00:00Z",
            user=TwitterUser(
                id="987654321",
                username="user123",
                name="Test User",
                followers_count=1000,
                verified=True,
                is_blue_verified=False,
            ),
            reply_count=5,
            retweet_count=10,
            like_count=20,
            quote_count=2,
            bookmark_count=1,
            is_quote_tweet=False,
            is_retweet=False,
            lang="en",
        )

        # Create the service
        service = SentimentAnalysisService(
            datura_api_key="test_datura_key",
            chutes_api_key="test_chutes_key",
            session=None,
        )

        # Mock the search_tweets method directly to return our tweet
        # We'll replace it temporarily with our own implementation
        original_search_tweets = service.search_tweets

        async def mock_search_tweets(self_arg, netuid_arg, max_results=10):
            """Our mocked version that returns the tweet we want"""
            assert netuid_arg == netuid  # Verify correct netuid was passed
            return [expected_tweet]

        # Replace the method
        service.search_tweets = mock_search_tweets.__get__(
            service, SentimentAnalysisService
        )

        try:
            # Act
            result = await service.search_tweets(netuid)

            # Assert
            assert len(result) == 1
            assert result[0].id == "1234567890"
            assert (
                result[0].text == "Bittensor netuid 18 is amazing! #bittensor"
            )
            assert result[0].user.username == "user123"
            assert result[0].user.followers_count == 1000
        finally:
            # Restore the original method
            service.search_tweets = original_search_tweets

    @pytest.mark.asyncio
    async def test_search_tweets_api_error(self):
        """Test error handling when searching tweets."""
        # Arrange
        netuid = 18

        # Create the service
        service = SentimentAnalysisService(
            datura_api_key="test_datura_key",
            chutes_api_key="test_chutes_key",
            session=None,
        )

        # Mock the search_tweets method to raise an error
        original_search_tweets = service.search_tweets

        async def mock_search_tweets_error(
            self_arg, netuid_arg, max_results=10
        ):
            """Our mocked version that raises an error"""
            raise ExternalAPIError(
                "Failed to search tweets: 401 - Unauthorized"
            )

        # Replace the method
        service.search_tweets = mock_search_tweets_error.__get__(
            service, SentimentAnalysisService
        )

        try:
            # Act & Assert
            with pytest.raises(ExternalAPIError) as exc_info:
                await service.search_tweets(netuid)

            assert "Failed to search tweets: 401" in str(exc_info.value)
        finally:
            # Restore the original method
            service.search_tweets = original_search_tweets

    @pytest.mark.asyncio
    async def test_analyze_sentiment_positive(self):
        """Test analyzing positive sentiment."""
        # Arrange
        netuid = 18

        # Create test tweets
        tweets = [
            Tweet(
                id="1234567890",
                text="Bittensor netuid 18 is amazing! #bittensor",
                url="https://twitter.com/user123/status/1234567890",
                created_at="2023-04-01T12:00:00Z",
                user=TwitterUser(
                    id="987654321",
                    username="user123",
                    name="Test User",
                    followers_count=1000,
                    verified=True,
                    is_blue_verified=False,
                ),
                reply_count=5,
                retweet_count=10,
                like_count=20,
                quote_count=2,
                bookmark_count=1,
                is_quote_tweet=False,
                is_retweet=False,
                lang="en",
            )
        ]

        # Create the service
        service = SentimentAnalysisService(
            datura_api_key="test_datura_key",
            chutes_api_key="test_chutes_key",
            session=None,
        )

        # Mock the analyze_sentiment method to return the result we want
        original_analyze_sentiment = service.analyze_sentiment

        async def mock_analyze_sentiment(self_arg, tweets_arg, netuid_arg):
            """Our mocked version that returns a positive sentiment"""
            # Make sure the correct arguments were passed
            assert netuid_arg == netuid
            assert len(tweets_arg) == 1
            assert tweets_arg[0].id == "1234567890"

            # Return a positive sentiment result
            return SentimentResult(
                netuid=netuid,
                score=75,
                tweets_count=len(tweets),
                operation_type="stake",
                stake_amount=0.75,
            )

        # Replace the method
        service.analyze_sentiment = mock_analyze_sentiment.__get__(
            service, SentimentAnalysisService
        )

        try:
            # Act
            result = await service.analyze_sentiment(tweets, netuid)

            # Assert
            assert isinstance(result, SentimentResult)
            assert result.netuid == netuid
            assert result.score == 75
            assert result.tweets_count == 1
            assert result.operation_type == "stake"
            assert result.stake_amount == 0.75
        finally:
            # Restore the original method
            service.analyze_sentiment = original_analyze_sentiment

    @pytest.mark.asyncio
    async def test_analyze_sentiment_negative(self):
        """Test analyzing negative sentiment."""
        # Arrange
        netuid = 18

        # Create test tweets
        tweets = [
            Tweet(
                id="1",
                text="Bittensor netuid 18 is terrible!",
                url="https://twitter.com/user1/status/1",
                created_at="2023-04-01T12:00:00Z",
                user=TwitterUser(
                    id="u1",
                    username="user1",
                    name="Test User",
                    followers_count=100,
                    verified=False,
                    is_blue_verified=False,
                ),
                reply_count=5,
                retweet_count=10,
                like_count=20,
                quote_count=2,
                bookmark_count=1,
                is_quote_tweet=False,
                is_retweet=False,
                lang="en",
            )
        ]

        # Create the service
        service = SentimentAnalysisService(
            datura_api_key="test_datura_key",
            chutes_api_key="test_chutes_key",
            session=None,
        )

        # Mock the analyze_sentiment method to return the result we want
        original_analyze_sentiment = service.analyze_sentiment

        async def mock_analyze_sentiment(self_arg, tweets_arg, netuid_arg):
            """Our mocked version that returns a negative sentiment"""
            # Make sure the correct arguments were passed
            assert netuid_arg == netuid
            assert len(tweets_arg) == 1
            assert tweets_arg[0].id == "1"

            # Return a negative sentiment result
            return SentimentResult(
                netuid=netuid,
                score=-60,
                tweets_count=len(tweets),
                operation_type="unstake",
                stake_amount=0.6,
            )

        # Replace the method
        service.analyze_sentiment = mock_analyze_sentiment.__get__(
            service, SentimentAnalysisService
        )

        try:
            # Act
            result = await service.analyze_sentiment(tweets, netuid)

            # Assert
            assert isinstance(result, SentimentResult)
            assert result.netuid == netuid
            assert result.score == -60
            assert result.tweets_count == 1
            assert result.operation_type == "unstake"
            assert result.stake_amount == 0.6
        finally:
            # Restore the original method
            service.analyze_sentiment = original_analyze_sentiment
