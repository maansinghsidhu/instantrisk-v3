"""
InstantRisk V2 - Configuration Settings

This module defines application settings using pydantic-settings
for environment variable management and validation.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application configuration settings.

    All settings can be overridden via environment variables.
    Environment variables should be prefixed based on the setting name.
    """

    # Application Settings
    app_name: str = "InstantRisk"
    app_version: str = "5.0.0"
    debug: bool = False
    environment: str = "production"

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    SECRET_KEY: str = ""

    # CORS Settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8200",
        "http://127.0.0.1:3000",
    ]

    # Database Settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "instantrisk_admin"
    postgres_password: str = ""
    postgres_db: str = "instantrisk"
    DATABASE_ECHO: bool = False

    @property
    def database_url(self) -> str:
        """Generate async database URL with SSL for RDS."""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}?ssl=require"

    @property
    def sync_database_url(self) -> str:
        """Generate sync database URL for migrations with SSL."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}?sslmode=require"

    # Redis Settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    REDIS_URL: str = ""

    @property
    def redis_url(self) -> str:
        """Generate Redis URL from host/port if not explicitly set."""
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # Qdrant Vector Database Settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "instantrisk_documents"

    # S3 Object Storage Settings (replaces MinIO)
    S3_DOCUMENTS_BUCKET: str = "instantrisk-documents-995306061991"
    S3_RAPIDRATE_BUCKET: str = "instantrisk-rapidrate-995306061991"
    S3_REGION: str = "us-east-1"

    # RapidRate Lambda Settings
    RAPIDRATE_LAMBDA_NAME: str = "instantrisk-rapidrate"
    RAPIDRATE_LAMBDA_REGION: str = "us-east-1"

    # JWT Settings
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # OpenAI Settings (legacy, replaced by Bedrock)
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"

    # AWS Bedrock Settings
    AWS_BEDROCK_REGION: str = "us-east-1"
    BEDROCK_MODEL_ID: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    BEDROCK_FALLBACK_MODEL: str = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    BEDROCK_ENABLED: bool = True

    # ClaimSense Settings
    CLAIMSENSE_API_URL: str = "https://vgyk08rvg4.execute-api.us-east-1.amazonaws.com/ucop-db-genai-insights-lambda"
    CLAIMSENSE_ENABLED: bool = True

    # OCR Settings
    OCR_LANGUAGES: List[str] = ["en", "ar", "fr"]

    # File Upload Settings
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    MAX_FILE_SIZE_MB: int = 50  # Used by S3 presigned URL conditions
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".doc", ".docx"]
    upload_dir: str = "/tmp/uploads"

    # Syndicate Domains for auto-recognition
    syndicate_domains: dict = {
        "beazley.com": {"syndicate": "623", "name": "Beazley"},
        "hiscox.com": {"syndicate": "33", "name": "Hiscox"},
        "tokiomarinekiln.com": {"syndicate": "510", "name": "Tokio Marine Kiln"},
        "lancashiregroup.com": {"syndicate": "2010", "name": "Lancashire"},
        "brit-insurance.com": {"syndicate": "2987", "name": "Brit"},
        "ascotgroup.com": {"syndicate": "1414", "name": "Ascot"},
        "convex.com": {"syndicate": "1955", "name": "Convex"},
        "argoglobal.com": {"syndicate": "1200", "name": "Argo"},
    }

    # Logging
    log_level: str = "INFO"

    # SMTP (optional)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: str = "noreply@instantrisk.com"

    # Lloyd's Data
    lloyds_syndicate_data_path: str = "./data/syndicates/lloyds_2025.json"

    # Google Cloud (optional)
    google_application_credentials: Optional[str] = None

    # Security Settings
    security_log_path: str = "/tmp/security.log"

    # CAPTCHA Settings (mCaptcha)
    MCAPTCHA_URL: str = "http://localhost:7000"
    MCAPTCHA_SITE_KEY: str = ""
    MCAPTCHA_SECRET_KEY: str = ""
    CAPTCHA_ENABLED: bool = False

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True

    # Circuit Breaker Thresholds
    CIRCUIT_BREAKER_HOURLY_AI_LIMIT: int = 500
    CIRCUIT_BREAKER_DAILY_COST_LIMIT_CENTS: int = 10000  # $100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
