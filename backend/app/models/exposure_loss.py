"""
InstantRisk V3 - Exposure Loss and Claims Models

Database models for tracking actual losses and claims per assessment/syndicate.
Enables calculation of loss ratios and combined ratios with real data.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
import enum

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Numeric, Text, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class LossType(enum.Enum):
    """Types of losses."""
    ATTRITIONAL = "attritional"
    LARGE_LOSS = "large_loss"
    CAT_LOSS = "cat_loss"
    RESERVE = "reserve"


class ClaimStatus(enum.Enum):
    """Claim processing status."""
    REPORTED = "reported"
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    PAID = "paid"
    CLOSED = "closed"
    DISPUTED = "disputed"


class ExposureLoss(Base):
    """
    Tracks actual losses against assessments/syndicates.

    Used for calculating incurred losses, loss ratios, and
    tracking loss development over time.
    """
    __tablename__ = "exposure_losses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=True)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id", ondelete="CASCADE"), nullable=False)

    # Loss details
    loss_date = Column(DateTime(timezone=True), nullable=False)
    loss_amount = Column(Numeric(precision=18, scale=2), nullable=False)
    currency = Column(String(3), default="GBP", nullable=False)
    loss_type = Column(SQLEnum(LossType, values_callable=lambda obj: [e.value for e in obj], native_enum=False), default=LossType.ATTRITIONAL, nullable=False)

    # Classification
    territory = Column(String(100), nullable=True)
    peril = Column(String(100), nullable=True)
    class_of_business = Column(String(100), nullable=True)

    # Description
    description = Column(Text, nullable=True)
    reference_number = Column(String(100), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships
    assessment = relationship("Assessment", back_populates="losses")
    syndicate = relationship("Syndicate", back_populates="losses")


class ExposureClaim(Base):
    """
    Tracks claims against assessments/syndicates.

    Used for claims management, reserve tracking, and
    calculating claims ratios.
    """
    __tablename__ = "exposure_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=True)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id", ondelete="CASCADE"), nullable=False)

    # Claim identification
    claim_number = Column(String(50), unique=True, nullable=False)
    claim_date = Column(DateTime(timezone=True), nullable=False)
    notification_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Financial
    claim_amount = Column(Numeric(precision=18, scale=2), nullable=False)
    reserve_amount = Column(Numeric(precision=18, scale=2), default=Decimal("0"))
    paid_amount = Column(Numeric(precision=18, scale=2), default=Decimal("0"))
    currency = Column(String(3), default="GBP", nullable=False)

    # Status
    status = Column(SQLEnum(ClaimStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False), default=ClaimStatus.REPORTED, nullable=False)

    # Classification
    cause = Column(String(200), nullable=True)
    territory = Column(String(100), nullable=True)
    peril = Column(String(100), nullable=True)
    class_of_business = Column(String(100), nullable=True)

    # Description
    description = Column(Text, nullable=True)
    claimant_name = Column(String(200), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    assessment = relationship("Assessment", back_populates="claims")
    syndicate = relationship("Syndicate", back_populates="claims")
