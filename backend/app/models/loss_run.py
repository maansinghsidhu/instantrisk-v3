"""
Loss Run Models

Database models for benchmark and insured loss run data.
Supports ClaimSense historical comparison and user-uploaded loss histories.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from enum import Enum

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Date,
    DateTime,
    Text,
    ForeignKey,
    Index,
    Float,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class ClaimType(str, Enum):
    """Standardized claim types."""
    BODILY_INJURY = "bodily_injury"
    PROPERTY_DAMAGE = "property_damage"
    MEDICAL = "medical"
    WORKERS_COMP = "workers_comp"
    AUTO_LIABILITY = "auto_liability"
    PROFESSIONAL_LIABILITY = "professional_liability"
    GENERAL_LIABILITY = "general_liability"
    PRODUCT_LIABILITY = "product_liability"
    OTHER = "other"


class ClaimStatus(str, Enum):
    """Claim status values."""
    OPEN = "open"
    CLOSED = "closed"
    REOPENED = "reopened"
    SUBROGATION = "subrogation"


class PolicyType(str, Enum):
    """Policy types for benchmarking."""
    GL = "GL"  # General Liability
    WC = "WC"  # Workers Compensation
    AL = "AL"  # Auto Liability
    PR = "PR"  # Property
    PL = "PL"  # Professional Liability
    CY = "CY"  # Cyber
    DO = "DO"  # Directors & Officers
    EPL = "EPL"  # Employment Practices Liability


class BenchmarkLossRun(Base):
    """
    Benchmark loss run data from ClaimSense (18K+ records).

    Used for industry/state/policy type comparisons.
    Data imported from Sandbox-01 DynamoDB AU_GL_PR_10_Yr_Loss_Run table.
    """
    __tablename__ = "benchmark_loss_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Classification
    policy_type = Column(String(10), nullable=False, index=True)
    state = Column(String(2), nullable=False, index=True)
    industry = Column(String(100), nullable=True, index=True)
    industry_code = Column(String(10), nullable=True)  # NAICS or SIC

    # Time period
    policy_year = Column(Integer, nullable=False, index=True)
    claim_date = Column(Date, nullable=True)
    report_date = Column(Date, nullable=True)

    # Claim details
    claim_type = Column(String(50), nullable=True)
    claim_description = Column(Text, nullable=True)

    # Financials
    amount_paid = Column(Numeric(15, 2), nullable=True, default=0)
    amount_reserved = Column(Numeric(15, 2), nullable=True, default=0)
    amount_incurred = Column(Numeric(15, 2), nullable=True)  # paid + reserved
    deductible = Column(Numeric(15, 2), nullable=True)

    # Metrics
    loss_ratio = Column(Float, nullable=True)
    claim_frequency = Column(Float, nullable=True)  # claims per $1M exposure
    severity = Column(Float, nullable=True)  # average claim amount

    # Metadata
    source = Column(String(50), nullable=True, default="claimsense")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_benchmark_policy_state", "policy_type", "state"),
        Index("ix_benchmark_policy_state_industry", "policy_type", "state", "industry"),
        Index("ix_benchmark_policy_year_range", "policy_type", "policy_year"),
    )

    def __repr__(self):
        return f"<BenchmarkLossRun {self.policy_type}/{self.state}/{self.policy_year}>"


class InsuredLossRun(Base):
    """
    User-uploaded loss run data for a specific assessment.

    Parsed from PDF/Excel/CSV uploads and compared against benchmarks.
    """
    __tablename__ = "insured_loss_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Link to assessment
    assessment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File reference
    raw_file_path = Column(String(500), nullable=True)  # S3 key
    raw_filename = Column(String(255), nullable=True)

    # Time period
    policy_year = Column(Integer, nullable=True)
    policy_effective_date = Column(Date, nullable=True)
    policy_expiration_date = Column(Date, nullable=True)

    # Claim details
    claim_number = Column(String(50), nullable=True)
    claim_date = Column(Date, nullable=True)
    report_date = Column(Date, nullable=True)
    close_date = Column(Date, nullable=True)

    claim_type = Column(String(50), nullable=True)
    claim_description = Column(Text, nullable=True)
    claimant_name = Column(String(255), nullable=True)

    status = Column(SQLEnum(ClaimStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False), nullable=True, default=ClaimStatus.OPEN)

    # Financials
    amount_paid = Column(Numeric(15, 2), nullable=True, default=0)
    amount_reserved = Column(Numeric(15, 2), nullable=True, default=0)
    amount_incurred = Column(Numeric(15, 2), nullable=True)
    expense_paid = Column(Numeric(15, 2), nullable=True, default=0)
    expense_reserved = Column(Numeric(15, 2), nullable=True, default=0)

    # Recovery
    subrogation_amount = Column(Numeric(15, 2), nullable=True, default=0)
    deductible_applied = Column(Numeric(15, 2), nullable=True, default=0)

    # Parsing metadata
    parsed_at = Column(DateTime, nullable=True)
    parsing_confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    parsing_notes = Column(Text, nullable=True)
    row_number = Column(Integer, nullable=True)  # original row in source file

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assessment = relationship("Assessment", back_populates="loss_runs")

    __table_args__ = (
        Index("ix_insured_assessment_year", "assessment_id", "policy_year"),
        Index("ix_insured_claim_date", "claim_date"),
    )

    def __repr__(self):
        return f"<InsuredLossRun {self.assessment_id}/{self.claim_number}>"

    @property
    def total_incurred(self) -> Decimal:
        """Calculate total incurred (paid + reserved)."""
        paid = self.amount_paid or Decimal(0)
        reserved = self.amount_reserved or Decimal(0)
        return paid + reserved

    @property
    def total_expense(self) -> Decimal:
        """Calculate total expense (paid + reserved)."""
        paid = self.expense_paid or Decimal(0)
        reserved = self.expense_reserved or Decimal(0)
        return paid + reserved


class LossRunSummary(Base):
    """
    Aggregated summary of loss runs for an assessment.

    Cached calculations for quick retrieval.
    """
    __tablename__ = "loss_run_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Counts
    total_claims = Column(Integer, default=0)
    open_claims = Column(Integer, default=0)
    closed_claims = Column(Integer, default=0)
    years_of_history = Column(Integer, default=0)

    # Financials
    total_paid = Column(Numeric(15, 2), default=0)
    total_reserved = Column(Numeric(15, 2), default=0)
    total_incurred = Column(Numeric(15, 2), default=0)

    # Metrics
    average_severity = Column(Float, nullable=True)
    claim_frequency = Column(Float, nullable=True)  # per policy year
    loss_ratio = Column(Float, nullable=True)

    # Largest claims
    largest_claim_amount = Column(Numeric(15, 2), nullable=True)
    largest_claim_type = Column(String(50), nullable=True)

    # By type breakdown (JSON stored as text)
    claims_by_type = Column(Text, nullable=True)  # JSON
    claims_by_year = Column(Text, nullable=True)  # JSON

    # Timestamps
    calculated_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<LossRunSummary {self.assessment_id}>"
