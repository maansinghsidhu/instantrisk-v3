"""
InstantRisk V2 - Sanctions Screening Models

Multi-level sanctions screening:
- Level 1: Quick Name Check (auto on assessment creation)
- Level 2: Enhanced Screening (auto after AI analysis)
- Level 3: Deep Analysis (user-triggered)
- Level 4: Full Investigation (user-triggered)
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text, Boolean
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from datetime import datetime
from enum import Enum

from ..core.database import Base


class ScreeningLevel(str, Enum):
    """Screening depth levels."""
    QUICK = "quick"           # Level 1: Basic name match against primary lists
    ENHANCED = "enhanced"     # Level 2: Fuzzy matching, aliases, related entities
    DEEP = "deep"             # Level 3: PEPs, adverse media, ownership chains
    FULL = "full"             # Level 4: Complete entity profile, network mapping


class ScreeningStatus(str, Enum):
    """Status of a screening."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CLEAR = "clear"
    REVIEW = "review"         # Potential match, needs review
    MATCH = "match"           # Confirmed match
    ERROR = "error"


class SanctionsScreening(Base):
    """
    Record of a sanctions screening for an assessment.

    Each assessment can have multiple screenings at different levels.
    Level 1 & 2 run automatically, Level 3 & 4 are user-triggered.
    """
    __tablename__ = "sanctions_screenings"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False, index=True)

    # Screening configuration
    screening_level = Column(SQLEnum(ScreeningLevel, values_callable=lambda obj: [e.value for e in obj], native_enum=False), default=ScreeningLevel.QUICK, nullable=False)
    status = Column(SQLEnum(ScreeningStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False), default=ScreeningStatus.PENDING, nullable=False)

    # Entities screened
    entities_screened = Column(Integer, default=0)
    matches_found = Column(Integer, default=0)
    highest_match_score = Column(Numeric(5, 2), default=0)

    # Sources checked
    sources_checked = Column(JSONB, default=list)  # ['OFAC', 'EU', 'UN', 'UK']

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Triggered by
    triggered_by = Column(String(50), default="system")  # 'system' or user_id
    is_auto = Column(Boolean, default=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assessment = relationship("Assessment", back_populates="sanctions_screenings")
    entities = relationship("SanctionsEntity", back_populates="screening", cascade="all, delete-orphan")


class SanctionsEntity(Base):
    """
    Individual entity checked during a sanctions screening.

    Stores the entity name, any matches found, and match details.
    """
    __tablename__ = "sanctions_entities"

    id = Column(Integer, primary_key=True, index=True)
    screening_id = Column(Integer, ForeignKey("sanctions_screenings.id"), nullable=False, index=True)

    # Entity info
    entity_name = Column(String(500), nullable=False)
    entity_type = Column(String(50), default="unknown")  # person, company, vessel, etc.
    entity_role = Column(String(100), nullable=True)  # insured, broker, beneficiary, etc.

    # Match results
    match_found = Column(Boolean, default=False)
    match_score = Column(Numeric(5, 2), default=0)  # 0-100 confidence
    match_reasons = Column(JSONB, default=list)  # ['exact_name', 'alias', 'fuzzy']

    # Matched entity details (from yente)
    matched_entity_id = Column(String(100), nullable=True)  # Entity ID from sanctions list
    matched_entity_name = Column(String(500), nullable=True)
    matched_entity_type = Column(String(50), nullable=True)
    sanctions_lists = Column(JSONB, default=list)  # ['OFAC SDN', 'EU Consolidated', etc.]
    aliases = Column(JSONB, default=list)  # Known aliases of matched entity

    # Extended info (Level 3+)
    pep_status = Column(Boolean, default=False)  # Politically Exposed Person
    pep_positions = Column(JSONB, default=list)  # List of political positions
    adverse_media = Column(JSONB, default=list)  # News articles, reports

    # Ownership (Level 4)
    ownership_chain = Column(JSONB, default=list)  # Parent companies, UBOs
    related_entities = Column(JSONB, default=list)  # Connected entities

    # Status
    status = Column(SQLEnum(ScreeningStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False), default=ScreeningStatus.PENDING)
    reviewed_by = Column(String(100), nullable=True)  # User who reviewed
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    screening = relationship("SanctionsScreening", back_populates="entities")


class SanctionsAlert(Base):
    """
    Alert generated when a match is found.

    Alerts can be acknowledged, dismissed, or escalated.
    """
    __tablename__ = "sanctions_alerts"

    id = Column(Integer, primary_key=True, index=True)
    screening_id = Column(Integer, ForeignKey("sanctions_screenings.id"), nullable=False)
    entity_id = Column(Integer, ForeignKey("sanctions_entities.id"), nullable=False)

    # Alert details
    alert_type = Column(String(50), default="match")  # match, pep, adverse_media
    severity = Column(String(20), default="medium")  # low, medium, high, critical
    message = Column(Text, nullable=False)

    # Status
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)

    is_dismissed = Column(Boolean, default=False)
    dismissed_reason = Column(Text, nullable=True)

    is_escalated = Column(Boolean, default=False)
    escalated_to = Column(String(100), nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
