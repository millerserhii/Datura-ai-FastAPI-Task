from pydantic import BaseModel, Field


class Tweet(BaseModel):
    """Twitter tweet model."""

    id: str
    text: str
    created_at: str
    author_username: str = Field(alias="username")
    author_id: str = Field(alias="author_id")

    class Config:
        populate_by_name = True


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
