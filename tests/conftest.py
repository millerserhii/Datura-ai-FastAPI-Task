from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from src.blockchain.models import DividendHistory, StakeTransaction
from src.blockchain.schemas import (
    StakeOperation,
    TaoDividend,
    TaoDividendsBatch,
)
from src.main import app
from src.sentiment.models import SentimentAnalysis
from src.sentiment.schemas import SentimentResult, Tweet
from src.sentiment.service import TwitterUser


# Override database URL for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    # Create the async engine
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        poolclass=NullPool,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Yield the engine itself, not an async generator
    yield engine

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create a test database session."""
    # Create a new sessionmaker with the test engine
    async_session = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Create and yield an actual session, not an async generator
    session = async_session()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


@pytest.fixture
def client():
    """Create a test client with overridden dependencies."""
    from fastapi.testclient import TestClient

    # Override session dependency
    async def override_get_session():
        yield None  # We'll mock the database operations

    # Override API key validation
    async def override_get_api_key():
        return "test_api_key"

    # Override dependencies
    from src.api.dependencies import get_api_key
    from src.database import get_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_api_key] = override_get_api_key

    # Create a synchronous test client
    test_client = TestClient(app)

    yield test_client

    # Clean up dependency overrides
    app.dependency_overrides.clear()


@pytest.fixture
def mock_api_key():
    """Mock API key for authenticated requests."""
    return "test_api_key"


@pytest.fixture
def mock_auth_header(mock_api_key):
    """Mock authorization header."""
    return {"Authorization": f"Bearer {mock_api_key}"}


# Fixture functions that create database model instances
@pytest.fixture
def create_dividend_history():
    """Create a DividendHistory instance."""

    async def _create_dividend_history(
        test_session,
        netuid=18,
        hotkey="5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v",
        dividend_value=1000,
        source="blockchain",
    ):
        dividend = DividendHistory(
            netuid=netuid,
            hotkey=hotkey,
            dividend_value=dividend_value,
            source=source,
            timestamp=datetime.utcnow(),
        )
        test_session.add(dividend)
        await test_session.commit()
        await test_session.refresh(dividend)
        return dividend

    return _create_dividend_history


@pytest.fixture
def create_stake_transaction():
    """Create a StakeTransaction instance."""

    async def _create_stake_transaction(
        test_session,
        operation_type="stake",
        netuid=18,
        hotkey="5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v",
        amount=1.5,
        tx_hash="0x1234567890abcdef",
        status="successful",
    ):
        transaction = StakeTransaction(
            operation_type=operation_type,
            netuid=netuid,
            hotkey=hotkey,
            amount=amount,
            tx_hash=tx_hash,
            status=status,
            timestamp=datetime.utcnow(),
        )
        test_session.add(transaction)
        await test_session.commit()
        await test_session.refresh(transaction)
        return transaction

    return _create_stake_transaction


@pytest.fixture
def create_sentiment_analysis():
    """Create a SentimentAnalysis instance."""

    async def _create_sentiment_analysis(
        test_session,
        netuid=18,
        score=75,
        tweets_count=10,
        operation_type="stake",
        stake_amount=0.75,
        tweets_text=None,
    ):
        analysis = SentimentAnalysis(
            netuid=netuid,
            score=score,
            tweets_count=tweets_count,
            operation_type=operation_type,
            stake_amount=stake_amount,
            tweets_text=tweets_text,
            timestamp=datetime.utcnow(),
        )
        test_session.add(analysis)
        await test_session.commit()
        await test_session.refresh(analysis)
        return analysis

    return _create_sentiment_analysis


# Mock schema objects
@pytest.fixture
def mock_tao_dividend():
    """Mock TaoDividend response."""
    return TaoDividend(
        netuid=18,
        hotkey="5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v",
        dividend=1000,
        cached=False,
    )


@pytest.fixture
def mock_tao_dividends_batch():
    """Mock TaoDividendsBatch response."""
    return TaoDividendsBatch(
        dividends=[
            TaoDividend(
                netuid=18,
                hotkey="5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v",
                dividend=1000,
                cached=False,
            ),
            TaoDividend(
                netuid=18,
                hotkey="5GrwvaEF5zXb26HamNNkHZryQoydSiMhPT3N6A8UJFDgZLGy",
                dividend=2000,
                cached=False,
            ),
        ],
        cached=False,
    )


@pytest.fixture
def mock_stake_operation():
    """Mock StakeOperation response."""
    return StakeOperation(
        hotkey="5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v",
        amount=1.5,
        operation_type="stake",
        tx_hash="0x1234567890abcdef",
        success=True,
    )


@pytest.fixture
def mock_sentiment_result():
    """Mock SentimentResult response."""
    return SentimentResult(
        netuid=18,
        score=75,
        tweets_count=10,
        operation_type="stake",
        stake_amount=0.75,
    )


@pytest.fixture
def mock_tweet():
    """Mock Tweet object with all required attributes."""
    return Tweet(
        id="1234567890",
        text="Bittensor netuid 18 is amazing! #bittensor",
        created_at="2023-04-01T12:00:00Z",
        author_username="user123",
        author_id="987654321",
        retweet_count=10,
        reply_count=5,
        quote_count=2,
        bookmark_count=1,
        user=TwitterUser(
            id="987654321",
            username="user123",
            name="Test User",
            followers_count=1000,
            verified=True,
            is_blue_verified=False,
        ),
    )


@pytest.fixture
def mock_twitter_user():
    """Mock TwitterUser object."""
    return TwitterUser(
        id="987654321",
        username="user123",
        name="Test User",
        followers_count=1000,
        verified=True,
        is_blue_verified=False,
    )


# Mocks for external services
@pytest.fixture
def mock_bittensor_client():
    """Mock BitensorClient for blockchain interactions."""
    with patch("src.blockchain.service.bittensor_client") as mock:
        mock.get_tao_dividends = AsyncMock()
        mock.stake = AsyncMock()
        mock.unstake = AsyncMock()
        yield mock


@pytest.fixture
def mock_redis_client():
    """Mock RedisClient for caching."""
    with patch("src.blockchain.service.redis_client") as mock:
        mock.get = AsyncMock()
        mock.set = AsyncMock()
        mock.delete = AsyncMock()
        mock.get_object = AsyncMock()
        mock.set_object = AsyncMock()
        yield mock


@pytest.fixture
def mock_celery_task():
    """Mock Celery task."""
    with patch(
        "src.api.v1.endpoints.tao_dividends.trigger_sentiment_analysis_and_stake"
    ) as mock:
        mock.delay.return_value = MagicMock(id="test-task-id")
        yield mock


@pytest.fixture
def mock_aiohttp_response():
    """Mock aiohttp response."""
    mock = AsyncMock()
    mock.status = 200
    mock.json = AsyncMock(return_value={})
    mock.text = AsyncMock(return_value="")
    return mock


@pytest.fixture
def mock_aiohttp_client_session(mock_aiohttp_response):
    """Mock aiohttp ClientSession with proper async context manager support."""
    # Create the session mock
    session_mock = AsyncMock()

    # Create a context manager mock for post
    cm_mock = AsyncMock()

    # Set up the context manager to return the response
    cm_mock.__aenter__.return_value = mock_aiohttp_response

    # Set up post to return the context manager
    session_mock.post.return_value = cm_mock

    # Return the session mock, configured correctly
    return session_mock


# Mock wallet access to avoid permission errors
@pytest.fixture(autouse=True)
def mock_wallet_path():
    """Mock wallet path to avoid file system access."""
    with patch("src.blockchain.client.BitensorClient.init_wallet"):
        yield


@pytest.fixture
def mock_session():
    """Mock database session."""
    return AsyncMock()
