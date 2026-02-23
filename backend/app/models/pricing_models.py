"""
Pricing and Quote Models

Extracted from lloyds.py for global underwriter platform.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DECIMAL,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.core.database import Base


class PricingModel(Base):
    """
    Stores pricing model configurations.
    """

    __tablename__ = "pricing_models"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), default="1.0")

    # Classification
    class_of_business = Column(String(50), nullable=True)
    model_type = Column(String(50), nullable=False)  # glm, xgboost, neural, rule_based

    # Model configuration
    parameters = Column(JSONB, default=dict)
    features = Column(ARRAY(String), default=list)

    # Performance
    performance_metrics = Column(JSONB, default=dict)  # {r2, mae, mape}

    # Status
    is_active = Column(Boolean, default=True)
    trained_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc)
    )


class PricingResult(Base):
    """
    Stores pricing calculation results.
    """

    __tablename__ = "pricing_results"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(
        PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False, index=True
    )
    model_id = Column(Integer, ForeignKey("pricing_models.id"), nullable=True)

    # Pricing output
    technical_premium = Column(DECIMAL(18, 2), nullable=False)
    currency = Column(String(3), default="GBP")

    # Risk assessment
    risk_score = Column(Float, nullable=True)  # 0-100
    risk_category = Column(String(20), nullable=True)  # low, medium, high, very_high

    # Confidence
    confidence_interval_low = Column(DECIMAL(18, 2), nullable=True)
    confidence_interval_high = Column(DECIMAL(18, 2), nullable=True)

    # Loading factors
    loading_factors = Column(JSONB, default=dict)
    # {cat_load, expense_load, profit_margin, etc.}

    # Explanation
    explanation = Column(JSONB, default=dict)
    key_drivers = Column(ARRAY(String), default=list)

    # Timestamp
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    assessment = relationship("Assessment", backref="pricing_results")
    model = relationship("PricingModel", backref="results")


class Quote(Base):
    """
    Formal quotes generated from pricing.
    Removed syndicate_id FK as platform now targets global underwriters.
    """

    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(
        PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False
    )
    pricing_result_id = Column(Integer, ForeignKey("pricing_results.id"), nullable=True)

    # Quote identification
    quote_reference = Column(String(50), unique=True, nullable=False, index=True)

    # Pricing
    quoted_premium = Column(DECIMAL(18, 2), nullable=False)
    currency = Column(String(3), default="GBP")
    quoted_line = Column(DECIMAL(5, 2), nullable=True)  # % line offered

    # Terms
    terms = Column(JSONB, default=dict)
    conditions = Column(ARRAY(String), default=list)
    subjectivities = Column(ARRAY(String), default=list)
    exclusions = Column(ARRAY(String), default=list)

    # Validity
    valid_from = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    valid_until = Column(DateTime(timezone=True), nullable=True)

    # Status
    status = Column(String(20), default="draft")
    # draft, issued, accepted, declined, expired, superseded

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    issued_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Broker portal fields
    accepted_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    declined_at = Column(DateTime(timezone=True), nullable=True)
    decline_reason = Column(Text, nullable=True)

    # Relationships
    assessment = relationship("Assessment", backref="quotes")
    pricing_result = relationship("PricingResult", backref="quotes")

    def to_dict(self):
        return {
            "quote_id": str(self.id),
            "assessment_id": str(self.assessment_id) if self.assessment_id else None,
            "quote_reference": self.quote_reference,
            "status": self.status,
            "quoted_premium": float(self.quoted_premium)
            if self.quoted_premium
            else None,
            "currency": self.currency,
            "terms": self.terms or {},
            "conditions": self.conditions or [],
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
        }
