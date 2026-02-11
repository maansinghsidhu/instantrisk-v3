"""
InstantRisk V2 - Assessment Model

This module defines the Assessment SQLAlchemy model for tracking
risk assessments with GO/NO-GO decisions.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, JSON, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class AssessmentStatus(str, enum.Enum):
    """Enumeration of assessment statuses."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AssessmentDecision(str, enum.Enum):
    """Enumeration of assessment decisions."""
    GO = "go"
    NO_GO = "no_go"
    REFER = "refer"
    PENDING = "pending"


class RiskCategory(str, enum.Enum):
    """Enumeration of risk categories."""
    PROPERTY = "property"
    CASUALTY = "casualty"
    MARINE = "marine"
    AVIATION = "aviation"
    ENERGY = "energy"
    SPECIALTY = "specialty"
    CYBER = "cyber"
    FINANCIAL_LINES = "financial_lines"


class Assessment(Base):
    """
    Assessment model for risk assessments.

    Attributes:
        id: Primary key identifier.
        reference_number: Unique reference number for the assessment.
        title: Title or summary of the risk.
        description: Detailed description of the risk.
        risk_category: Category of the risk being assessed.
        status: Current status of the assessment.
        decision: GO/NO-GO/REFER decision.
        created_by: Foreign key to the user who created the assessment.
        syndicate_id: Foreign key to the target syndicate.
        insured_name: Name of the insured party.
        broker_reference: Broker's reference number.
        premium: Quoted premium amount.
        sum_insured: Total sum insured.
        inception_date: Policy inception date.
        expiry_date: Policy expiry date.
        territory: Primary territory/region.
        risk_score: AI-calculated risk score (0-100).
        confidence_score: AI confidence in the assessment (0-100).
        ai_analysis: JSON field containing detailed AI analysis.
        ai_recommendations: JSON array of AI recommendations.
        underwriter_notes: Manual notes from underwriter.
        decision_rationale: Explanation of the decision.
        created_at: Timestamp when the assessment was created.
        updated_at: Timestamp when the assessment was last updated.
        completed_at: Timestamp when the assessment was completed.
    """

    __tablename__ = "assessments"

    # Note: EC2 database uses UUID for assessment IDs
    id = Column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    # Made nullable=True for compatibility with EC2 database that lacks this column
    reference_number = Column(String(50), unique=True, index=True, nullable=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Classification
    risk_category = Column(
        Enum(RiskCategory, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=RiskCategory.PROPERTY,
        nullable=False
    )

    # Status and decision
    status = Column(
        Enum(AssessmentStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=AssessmentStatus.DRAFT,
        nullable=False,
        index=True
    )
    decision = Column(
        Enum(AssessmentDecision, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=AssessmentDecision.PENDING,
        nullable=False,
        index=True
    )

    # Relationships
    created_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=True)

    # Risk details
    insured_name = Column(String(255), nullable=True)
    broker_reference = Column(String(100), nullable=True)
    premium = Column(Float, nullable=True, comment="Premium in GBP")
    sum_insured = Column(Float, nullable=True, comment="Sum insured in GBP")
    deductible = Column(Float, nullable=True, comment="Deductible in GBP")

    # Policy dates
    inception_date = Column(DateTime(timezone=True), nullable=True)
    expiry_date = Column(DateTime(timezone=True), nullable=True)

    # Territory and exposure
    territory = Column(String(100), nullable=True)
    exposure_details = Column(JSON, default=dict)

    # AI analysis results
    risk_score = Column(Integer, nullable=True, comment="Risk score 0-100 (higher = riskier)")
    confidence_score = Column(Integer, nullable=True, comment="AI confidence 0-100")
    ai_analysis = Column(
        JSON,
        default=dict,
        comment="Detailed AI analysis results"
    )
    ai_recommendations = Column(
        JSON,
        default=list,
        comment="AI-generated recommendations"
    )

    # Analysis mode tracking (for upgrade capability)
    analysis_mode = Column(
        String(20),
        nullable=True,
        comment="Analysis depth: quick/go_no_go/deep"
    )
    previous_analysis_json = Column(
        JSON,
        nullable=True,
        comment="Prior analysis results if upgraded from lower mode"
    )

    # Manual inputs
    underwriter_notes = Column(Text, nullable=True)
    decision_rationale = Column(Text, nullable=True)

    # OCR extracted text
    ocr_extracted_text = Column(Text, nullable=True, comment="Full OCR extracted text from documents")

    # Audit flags
    is_flagged = Column(Boolean, default=False, comment="Flagged for review")
    flag_reason = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    created_by_user = relationship("User", back_populates="assessments")
    syndicate = relationship("Syndicate", back_populates="assessments")
    documents = relationship("Document", back_populates="assessment")
    generated_documents = relationship("GeneratedDocument", back_populates="assessment", cascade="all, delete-orphan")
    generation_jobs = relationship("DocumentGenerationJob", back_populates="assessment", cascade="all, delete-orphan")
    upload_session = relationship("UploadSession", back_populates="assessment", uselist=False)
    losses = relationship("ExposureLoss", back_populates="assessment", cascade="all, delete-orphan")
    claims = relationship("ExposureClaim", back_populates="assessment", cascade="all, delete-orphan")
    sanctions_screenings = relationship("SanctionsScreening", back_populates="assessment", cascade="all, delete-orphan")
    loss_runs = relationship("InsuredLossRun", back_populates="assessment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation of the Assessment."""
        return f"<Assessment(id={self.id}, ref='{self.reference_number}', decision='{self.decision}')>"

    def set_decision(self, decision: AssessmentDecision, rationale: str) -> None:
        """
        Set the assessment decision with rationale.

        Args:
            decision: The GO/NO-GO/REFER decision.
            rationale: Explanation for the decision.
        """
        self.decision = decision
        self.decision_rationale = rationale
        if decision != AssessmentDecision.PENDING:
            self.status = AssessmentStatus.COMPLETED
            self.completed_at = datetime.now(timezone.utc)

    def calculate_risk_rating(self) -> str:
        """
        Calculate a risk rating based on the risk score.

        Returns:
            str: Risk rating (Low, Medium, High, Very High).
        """
        if self.risk_score is None:
            return "Unknown"
        if self.risk_score < 25:
            return "Low"
        elif self.risk_score < 50:
            return "Medium"
        elif self.risk_score < 75:
            return "High"
        else:
            return "Very High"

    @property
    def is_within_appetite(self) -> bool:
        """
        Check if the assessment is within syndicate's risk appetite.

        Returns:
            bool: True if within appetite, False otherwise.
        """
        if self.syndicate is None:
            return True
        return self.syndicate.is_in_risk_appetite({
            "risk_score": self.risk_score,
            "premium": self.premium,
            "sum_insured": self.sum_insured
        })
