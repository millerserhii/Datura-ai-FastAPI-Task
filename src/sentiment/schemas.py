from pydantic import BaseModel, Field


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


class TweetBatch(BaseModel):
    """Batch of tweets."""

    tweets: list[Tweet]
    query: str
    count: int = Field(default=0)

    def __init__(self, **data):
        super().__init__(**data)
        self.count = len(self.tweets)


class SentimentResult(BaseModel):
    """Sentiment analysis result model."""

    netuid: int
    score: int  # -100 to +100
    tweets_count: int
    operation_type: str  # "stake" or "unstake"
    stake_amount: float
