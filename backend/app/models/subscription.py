"""
InstantRisk V2 - Subscription Model

This module defines the Subscription SQLAlchemy model for managing user subscriptions
with tiered access (Basic, Premium, Trial).
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class SubscriptionTier(str, enum.Enum):
    """Enumeration of subscription tiers."""
    TRIAL = "trial"
    BASIC = "basic"
    PREMIUM = "premium"


class SubscriptionStatus(str, enum.Enum):
    """Enumeration of subscription statuses."""
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Subscription(Base):
    """
    Subscription model representing user subscription plans.

    Attributes:
        id: Primary key identifier.
        user_id: Foreign key to the user.
        tier: Subscription tier (trial, basic, premium).
        status: Current subscription status.
        started_at: When the subscription started.
        expires_at: When the subscription expires.
        stripe_customer_id: Stripe customer ID for payment processing.
        stripe_subscription_id: Stripe subscription ID.
        monthly_assessments_used: Number of assessments used this month.
        monthly_documents_generated: Number of documents generated this month.
        monthly_chat_messages_used: Number of chat messages used this month.
        usage_reset_at: When usage counters were last reset.
    """

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)

    tier = Column(
        Enum(SubscriptionTier, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=SubscriptionTier.TRIAL,
        nullable=False
    )
    status = Column(
        Enum(SubscriptionStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=SubscriptionStatus.PENDING,
        nullable=False
    )

    started_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Payment integration (for future use)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)

    # Usage tracking
    monthly_assessments_used = Column(Integer, default=0)
    monthly_documents_generated = Column(Integer, default=0)
    monthly_chat_messages_used = Column(Integer, default=0)
    usage_reset_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = relationship("User", back_populates="subscription")

    def __repr__(self) -> str:
        """String representation of the Subscription."""
        return f"<Subscription(id={self.id}, user_id={self.user_id}, tier='{self.tier}', status='{self.status}')>"

    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return False
        return True

    def has_feature(self, feature_name: str) -> bool:
        """Check if subscription tier has access to a feature."""
        from app.models.feature_limits import TIER_LIMITS
        tier_config = TIER_LIMITS.get(self.tier, TIER_LIMITS[SubscriptionTier.BASIC])
        return tier_config.get("features", {}).get(feature_name, False)

    def get_limit(self, limit_name: str) -> int:
        """Get the limit value for a specific resource."""
        from app.models.feature_limits import TIER_LIMITS
        tier_config = TIER_LIMITS.get(self.tier, TIER_LIMITS[SubscriptionTier.BASIC])
        return tier_config.get(limit_name, 0)

    def can_use_analysis_mode(self, mode: str) -> bool:
        """Check if subscription tier can use a specific analysis mode."""
        from app.models.feature_limits import TIER_LIMITS
        tier_config = TIER_LIMITS.get(self.tier, TIER_LIMITS[SubscriptionTier.BASIC])
        return mode in tier_config.get("analysis_modes", [])

    def increment_usage(self, usage_type: str, amount: int = 1) -> None:
        """Increment usage counter for a specific resource type."""
        if usage_type == "assessments":
            self.monthly_assessments_used += amount
        elif usage_type == "documents":
            self.monthly_documents_generated += amount
        elif usage_type == "chat_messages":
            self.monthly_chat_messages_used += amount

    def reset_usage(self) -> None:
        """Reset all usage counters (called monthly)."""
        self.monthly_assessments_used = 0
        self.monthly_documents_generated = 0
        self.monthly_chat_messages_used = 0
        self.usage_reset_at = datetime.now(timezone.utc)
