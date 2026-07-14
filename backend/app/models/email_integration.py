"""
InstantRisk V3 - Email Integration Models

SQLAlchemy models for user-connected email ingestion:
- EmailConnection: per-user Gmail/Outlook OAuth or IMAP connections
- EmailIngestionEvent: deduped ingestion events per provider message ID
"""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Integer,
    Text,
    ForeignKey,
    Enum,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class EmailProvider(str, enum.Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"


class ConnectionStatus(str, enum.Enum):
    ACTIVE = "active"
    ERROR = "error"
    DISCONNECTED = "disconnected"
    PENDING_REAUTH = "pending_reauth"


class AuthMethod(str, enum.Enum):
    OAUTH = "oauth"
    IMAP_APP_PASSWORD = "imap_app_password"


class EmailConnection(Base):
    """
    Per-user email connection for automated inbox ingestion.

    AuthMethod determines how credentials are stored:
    - OAUTH: encrypted access_token + refresh_token (Fernet)
    - IMAP_APP_PASSWORD: encrypted app-specific password (Fernet)

    Tokens/passwords are NEVER exposed via API.
    """

    __tablename__ = "email_connections"

    id = Column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Provider identity
    provider = Column(Enum(EmailProvider, values_callable=lambda obj: [e.value for e in obj], native_enum=False), nullable=False)
    auth_method = Column(Enum(AuthMethod, values_callable=lambda obj: [e.value for e in obj], native_enum=False), nullable=False, default=AuthMethod.OAUTH)

    # Human-readable account info (no secrets)
    email_address = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)

    # Status
    status = Column(Enum(ConnectionStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False), nullable=False, default=ConnectionStatus.ACTIVE)
    error_message = Column(Text, nullable=True)

    # OAuth tokens: encrypted at rest, never in schemas/logs
    # IMAP password: also encrypted at rest
    _encrypted_access_token = Column("encrypted_access_token", Text, nullable=True)
    _encrypted_refresh_token = Column("encrypted_refresh_token", Text, nullable=True)
    _encrypted_app_password = Column("encrypted_app_password", Text, nullable=True)  # IMAP only
    _encrypted_client_secret = Column("encrypted_client_secret", Text, nullable=True)  # OAuth client secret

    # OAuth expiry tracking (UTC)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # IMAP host tracking (restricted to known hosts)
    imap_host = Column(String(255), nullable=True)  # imap.gmail.com or outlook.office365.com
    imap_port = Column(Integer, nullable=True, default=993)

    # OAuth: PKCE state nonce (transient, not persisted beyond callback)
    # Stored in Redis instead, keyed by state token

    # Sync state
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    total_messages_synced = Column(Integer, default=0)
    consecutive_errors = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="email_connections")
    ingestion_events = relationship("EmailIngestionEvent", back_populates="connection", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_email_connections_user_provider", "user_id", "provider"),
        UniqueConstraint("user_id", "email_address", name="uq_email_connections_user_email"),
    )

    def __repr__(self) -> str:
        return f"<EmailConnection(id={self.id}, provider={self.provider}, email={self.email_address})>"


class EmailIngestionEvent(Base):
    """
    Deduplication record for ingested emails.

    For OAuth (Gmail/Outlook Graph):
      dedupe_key = provider_message_id  (e.g. Gmail message ID "12345")
    For IMAP:
      dedupe_key = UIDVALIDITY:UID  (e.g. "1234:56789")

    Each user+connection+message combination is unique.
    """

    __tablename__ = "email_ingestion_events"

    id = Column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(PgUUID(as_uuid=True), ForeignKey("email_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Deduplication key
    # Gmail/Outlook Graph: provider's immutable message ID
    # IMAP: UIDVALIDITY:UID (e.g. "1234:56789")
    dedupe_key = Column(String(255), nullable=False)

    # Message metadata
    subject = Column(String(1000), nullable=True)
    sender = Column(String(500), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)

    # Processing outcome
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=True)
    document_ids = Column(Text, nullable=True)  # JSON array of document IDs
    parse_confidence = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    processed = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    connection = relationship("EmailConnection", back_populates="ingestion_events")

    __table_args__ = (
        Index("ix_email_ingestion_events_connection_dedupe", "connection_id", "dedupe_key"),
        UniqueConstraint("connection_id", "dedupe_key", name="uq_ingestion_dedupe"),
    )

    def __repr__(self) -> str:
        return f"<EmailIngestionEvent(id={self.id}, dedupe_key={self.dedupe_key})>"
