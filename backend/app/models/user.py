"""
InstantRisk V2 - User Model

This module defines the User SQLAlchemy model with role-based access control.
Supports broker, syndicate, and admin roles.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Text,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
import uuid as uuid_mod
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class UserRole(str, enum.Enum):
    """Enumeration of user roles in the system."""

    BROKER = "broker"
    SYNDICATE = "syndicate"
    ADMIN = "admin"
    UNDERWRITER = "underwriter"


class ApprovalStatus(str, enum.Enum):
    """Enumeration of account approval statuses."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SupportedLanguage(str, enum.Enum):
    """Supported languages for the application and document generation."""

    ENGLISH = "en"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    DUTCH = "nl"
    ARABIC = "ar"
    CHINESE = "zh"
    JAPANESE = "ja"


class User(Base):
    """
    User model representing system users.

    Attributes:
        id: Primary key identifier.
        email: Unique email address for authentication.
        hashed_password: Bcrypt hashed password.
        full_name: User's full name.
        role: User role (broker, syndicate, or admin).
        syndicate_id: Foreign key to syndicate (for syndicate users).
        is_active: Whether the user account is active.
        is_verified: Whether the email has been verified.
        created_at: Timestamp when the user was created.
        updated_at: Timestamp when the user was last updated.
        last_login: Timestamp of the last successful login.
    """

    __tablename__ = "users"

    id = Column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4, index=True
    )
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(
        Enum(
            UserRole,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=UserRole.BROKER,
        nullable=False,
    )
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Account approval workflow
    approval_status = Column(
        Enum(
            ApprovalStatus,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=ApprovalStatus.PENDING,
        nullable=False,
    )
    approved_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Language preference for UI and document generation
    preferred_language = Column(
        Enum(
            SupportedLanguage,
            values_callable=lambda obj: [e.value for e in obj],
            native_enum=False,
        ),
        default=SupportedLanguage.ENGLISH,
        nullable=False,
    )

    # Two-Factor Authentication (2FA)
    two_fa_enabled = Column(Boolean, default=False)
    two_fa_secret = Column(String(32), nullable=True)  # Base32 encoded TOTP secret
    two_fa_backup_codes = Column(
        Text, nullable=True
    )  # JSON array of hashed backup codes

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Broker-specific: default commission rate (percentage, e.g. 15.0 = 15%)
    commission_rate = Column(
        Float, nullable=True, comment="Default commission rate % for broker"
    )

    # Relationships
    syndicate = relationship("Syndicate", back_populates="users")
    assessments = relationship(
        "Assessment",
        foreign_keys="Assessment.created_by",
        back_populates="created_by_user",
    )
    documents = relationship("Document", back_populates="uploaded_by_user")
    upload_sessions = relationship("UploadSession", back_populates="user")
    templates = relationship("Template", back_populates="created_by_user")
    template_favorites = relationship(
        "TemplateFavorite", back_populates="user", cascade="all, delete-orphan"
    )
    reference_documents = relationship(
        "ReferenceDocument", back_populates="uploaded_by_user"
    )
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    approved_by_user = relationship(
        "User", remote_side="User.id", foreign_keys=[approved_by]
    )

    def __repr__(self) -> str:
        """String representation of the User."""
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
