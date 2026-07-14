"""
InstantRisk V2 - Configuration Settings

This module defines application settings using pydantic-settings
for environment variable management and validation.
"""

import os
import tempfile
import hashlib
import base64
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

    # Trusted proxies for X-Forwarded-For / X-Real-IP. Only requests
    # arriving from these IPs/CIDRs are allowed to override the client
    # IP. Defaults to the InstantRisk ALB's subnets (10.0.101.0/24,
    # 10.0.102.0/24) plus loopback. Broad ranges like 10.0.0.0/8 let
    # any host in the VPC forge the captured client IP.
    trusted_proxies: List[str] = [
        "10.0.101.0/24",   # ALB subnet, us-east-1a
        "10.0.102.0/24",   # ALB subnet, us-east-1b
        "127.0.0.1/32",    # loopback (health checks, ECS exec)
    ]
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "instantrisk_admin"
    postgres_password: str = ""
    postgres_db: str = "instantrisk"
    DATABASE_ECHO: bool = False
    DATABASE_URL: str = ""

    @property
    def database_url(self) -> str:
        """Generate async database URL. Adds SSL for non-development environments."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        base = f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        if self.environment != "development":
            base += "?ssl=require"
        return base

    @property
    def sync_database_url(self) -> str:
        """Generate sync database URL for migrations. Adds SSL for non-development environments."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL.replace("+asyncpg", "")
            return url
        base = f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        if self.environment != "development":
            base += "?sslmode=require"
        return base

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

    # pgvector (vector search via PostgreSQL — replaces Qdrant)
    PGVECTOR_ENABLED: bool = True

    # S3 Object Storage Settings (replaces MinIO)
    S3_DOCUMENTS_BUCKET: str = "instantrisk-documents-995306061991"
    S3_RAPIDRATE_BUCKET: str = "instantrisk-rapidrate-995306061991"
    S3_REGION: str = "us-east-1"
    # Pricing for billing summary MRR calculation. Override per environment
    # via TIER_PRICE_USD_TRIAL / TIER_PRICE_USD_BASIC / TIER_PRICE_USD_PREMIUM
    # env vars. Pydantic's JSON parsing is used so the env value can be
    # either a JSON object {"trial": 0, "basic": 99, "premium": 499} or
    # three individual variables.
    tier_price_usd: dict = {
        "trial": 0,
        "basic": 99,
        "premium": 499,
    }

    # RapidRate Lambda Settings
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
    BEDROCK_FALLBACK_MODEL: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
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
    upload_dir: str = ""  # Set via UPLOAD_DIR env var; defaults to tempfile.gettempdir()/uploads at runtime

    @property
    def resolved_upload_dir(self) -> str:
        return self.upload_dir or os.path.join(tempfile.gettempdir(), "uploads")

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
    security_log_path: str = ""  # Set via SECURITY_LOG_PATH env var

    @property
    def resolved_security_log_path(self) -> str:
        return self.security_log_path or os.path.join(tempfile.gettempdir(), "security.log")

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

    # Email Integration (OAuth + IMAP ingestion)
    # OAuth: set GOOGLE_CLIENT_ID/SECRET and/or MICROSOFT_CLIENT_ID/SECRET
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    # Override to change OAuth callback base URL (defaults to first CORS_ORIGIN)
    EMAIL_OAUTH_REDIRECT_BASE: str = ""
    # Fernet key for encrypting OAuth tokens and IMAP passwords at rest.
    # If not set, derived from SECRET_KEY[:32] (less secure — set explicitly in prod).
    EMAIL_TOKEN_ENCRYPTION_KEY: str = ""
    # Background sync interval in seconds (default 5 minutes)
    EMAIL_SYNC_INTERVAL_SECONDS: int = 300

    @property
    def resolved_email_encryption_key(self) -> str:
        """Return a valid Fernet key without weakening configured entropy."""
        raw = self.EMAIL_TOKEN_ENCRYPTION_KEY or self.SECRET_KEY
        if not raw:
            return ""

        # Preserve an explicitly generated Fernet key. For legacy arbitrary
        # secrets, derive 32 bytes with SHA-256 and encode them for Fernet.
        try:
            decoded = base64.urlsafe_b64decode(raw.encode())
            if len(decoded) == 32:
                return raw
        except (ValueError, TypeError):
            pass
        return base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()).decode()

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
