"""Application configuration settings using pydantic-settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Order Orchestrator Engine"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database Settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "orchestrator_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/orchestrator_db"

    # Connection Pool Settings
    DB_POOL_MIN_SIZE: int = 0
    DB_POOL_MAX_SIZE: int = 10
    DB_POOL_TIMEOUT: float = 2.0

    # Mock APIs Toggle (Enable for offline dev and unit tests)
    USE_MOCK_APIS: bool = True

    # External API Base URLs
    ORDER_API_URL: str = "https://api.store.internal/v1/orders"
    INVENTORY_API_URL: str = "https://api.warehouse.internal/v1/inventory"
    SHIPPING_API_URL: str = "https://api.logistics.internal/v1/shipping"
    NOTIFICATION_API_URL: str = "https://api.comms.internal/v1/notifications"

    # HTTP Client Configuration (Layer 1)
    HTTP_TIMEOUT_SECONDS: float = 30.0
    HTTP_MAX_RETRIES: int = 3
    HTTP_BACKOFF_FACTOR: float = 0.5

    # LangGraph Node Execution Retry Configuration (Layer 2)
    NODE_MAX_RETRIES: int = 3
    NODE_RETRY_INITIAL_INTERVAL: float = 1.0
    NODE_RETRY_BACKOFF_FACTOR: float = 2.0
    NODE_RETRY_MAX_INTERVAL: float = 10.0
    NODE_RETRY_JITTER: bool = True

    # OAuth2 Client Credentials Settings
    OAUTH_TOKEN_URL: str = "https://auth.internal/oauth/token"
    OAUTH_CLIENT_ID: Optional[str] = None
    OAUTH_CLIENT_SECRET: Optional[str] = None
    OAUTH_SCOPES: Optional[str] = "orders:read inventory:write shipping:write"

    # Multi-Model LLM Configuration
    DEFAULT_LLM_PROVIDER: str = "gemini"  # "gemini" or "claude"
    ENABLE_LLM_FALLBACK: bool = True

    # Google Gemini Settings
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.2

    # Anthropic Claude Settings
    ANTHROPIC_API_KEY: Optional[str] = None
    CLAUDE_MODEL: str = "claude-3-7-sonnet-20250219"
    CLAUDE_TEMPERATURE: float = 0.2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
