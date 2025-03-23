# mypy: disable-error-code="call-arg"
from typing import Optional

from pydantic import PostgresDsn, RedisDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # API
    API_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Tao Dividends API"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Server
    PORT: int = 8000

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Authentication
    API_AUTH_TOKEN: SecretStr

    # Database
    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: SecretStr
    DB_NAME: str = "app"
    DATABASE_URL: Optional[PostgresDsn] = None

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: SecretStr
    REDIS_URL: Optional[RedisDsn] = None

    # Cache TTL (in seconds)
    CACHE_TTL: int = 120  # 2 minutes

    # Bittensor
    BT_NETWORK: str = "test"  # or finney
    BT_WALLET_NAME: str
    BT_WALLET_HOTKEY: str
    BT_WALLET_SEED: SecretStr

    # External APIs
    DATURA_API_KEY: SecretStr
    CHUTES_API_KEY: SecretStr

    # Default parameters
    DEFAULT_NETUID: int
    DEFAULT_HOTKEY: SecretStr

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.DATABASE_URL:
            password = (
                self.DB_PASSWORD.get_secret_value()
                if isinstance(self.DB_PASSWORD, SecretStr)
                else self.DB_PASSWORD
            )

            self.DATABASE_URL = PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.DB_USER,
                password=password,
                host=self.DB_HOST,
                port=self.DB_PORT,
                path=self.DB_NAME,
            )
            print(self.DATABASE_URL)
        return self

    @model_validator(mode="after")
    def build_redis_url(self) -> "Settings":
        if not self.REDIS_URL:
            password = (
                self.REDIS_PASSWORD.get_secret_value()
                if isinstance(self.REDIS_PASSWORD, SecretStr)
                else self.REDIS_PASSWORD
            )

            self.REDIS_URL = RedisDsn.build(
                scheme="redis",
                username="default",
                password=password,
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                path="/0",
            )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True
        validate_default = True


settings = Settings()
