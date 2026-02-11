"""
InstantRisk V3 - Extraction Models

This module defines database models for:
- Extraction results and metadata
- Human feedback/corrections
- Training data collection
- Accuracy metrics tracking
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, JSON,
    ForeignKey, Enum, Float, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class ExtractionConfidenceLevel(str, enum.Enum):
    """Extraction confidence level classification."""
    HIGH = "high"       # > 90% - Auto-accept
    MEDIUM = "medium"   # 70-90% - Highlight for review
    LOW = "low"         # < 70% - Flag for manual entry


class ExtractionStatus(str, enum.Enum):
    """Status of document extraction."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class CorrectionType(str, enum.Enum):
    """Type of correction made to an extraction."""
    MISSING_VALUE = "missing_value"       # Field was empty, now has value
    FALSE_POSITIVE = "false_positive"     # Incorrectly detected field
    WRONG_VALUE = "wrong_value"           # Value was incorrect
    FORMATTING = "formatting"             # Value format needed adjustment
    TYPE_MISMATCH = "type_mismatch"       # Data type was wrong


class DocumentExtraction(Base):
    """
    Stores extraction results for documents.

    Links to the original document and tracks extraction metadata,
    confidence scores, and validation status.
    """

    __tablename__ = "document_extractions"

    id = Column(Integer, primary_key=True, index=True)

    # Link to original document
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)

    # Document type detection
    detected_type = Column(String(50), nullable=False, comment="Detected document type")
    type_confidence = Column(Float, nullable=False, default=0.0, comment="Document type detection confidence")
    type_confidence_level = Column(
        Enum(ExtractionConfidenceLevel, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=ExtractionConfidenceLevel.LOW,
        nullable=False
    )
    matched_keywords = Column(JSON, default=list, comment="Keywords matched during type detection")
    matched_sections = Column(JSON, default=list, comment="Document sections matched")

    # Extraction status
    status = Column(
        Enum(ExtractionStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=ExtractionStatus.PARTIAL,
        nullable=False,
        index=True
    )

    # Extracted data (full extraction result)
    extracted_data = Column(JSON, default=dict, comment="All extracted fields with metadata")

    # Validation results
    is_valid = Column(Boolean, default=False, nullable=False)
    completeness_score = Column(Float, default=0.0, comment="Extraction completeness 0-1")
    required_fields_found = Column(JSON, default=list)
    required_fields_missing = Column(JSON, default=list)
    validation_errors = Column(JSON, default=list)
    validation_warnings = Column(JSON, default=list)

    # Overall confidence
    overall_confidence = Column(Float, default=0.0, comment="Overall extraction confidence 0-100")
    overall_confidence_level = Column(
        Enum(ExtractionConfidenceLevel, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=ExtractionConfidenceLevel.LOW,
        nullable=False
    )
    fields_requiring_review = Column(JSON, default=list, comment="Fields flagged for human review")

    # Processing metadata
    processing_time_ms = Column(Float, default=0.0, comment="Extraction processing time in ms")
    rag_context_used = Column(Boolean, default=False)
    similar_documents_found = Column(Integer, default=0)
    raw_text_hash = Column(String(64), nullable=True, comment="Hash of source text for caching")

    # Review status
    reviewed = Column(Boolean, default=False, comment="Has been reviewed by human")
    reviewed_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    document = relationship("Document", back_populates="extractions")
    corrections = relationship("ExtractionCorrection", back_populates="extraction", cascade="all, delete-orphan")
    training_samples = relationship("TrainingSample", back_populates="extraction", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('ix_extraction_doc_status', 'document_id', 'status'),
        Index('ix_extraction_confidence', 'overall_confidence'),
        Index('ix_extraction_type', 'detected_type'),
    )

    def __repr__(self) -> str:
        return f"<DocumentExtraction(id={self.id}, document_id={self.document_id}, status='{self.status}')>"

    def mark_reviewed(self, user_id: str) -> None:
        """Mark extraction as reviewed by a user."""
        self.reviewed = True
        self.reviewed_by = user_id
        self.reviewed_at = datetime.now(timezone.utc)


class ExtractionCorrection(Base):
    """
    Stores human corrections to extracted fields.

    Used to track accuracy, improve patterns, and build training data.
    """

    __tablename__ = "extraction_corrections"

    id = Column(Integer, primary_key=True, index=True)

    # Link to extraction
    extraction_id = Column(Integer, ForeignKey("document_extractions.id"), nullable=False, index=True)

    # Field identification
    field_name = Column(String(100), nullable=False, index=True, comment="Name of corrected field")
    field_path = Column(String(255), nullable=True, comment="Full path for nested fields")

    # Values
    original_value = Column(JSON, nullable=True, comment="Original extracted value")
    corrected_value = Column(JSON, nullable=True, comment="Human-corrected value")

    # Original extraction metadata
    original_confidence = Column(Float, nullable=True, comment="Original confidence score")
    extraction_pattern = Column(Text, nullable=True, comment="Pattern used for extraction")

    # Correction metadata
    correction_type = Column(
        Enum(CorrectionType, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=CorrectionType.WRONG_VALUE,
        nullable=False
    )
    correction_reason = Column(Text, nullable=True, comment="Optional reason for correction")

    # User who made correction
    corrected_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Processing flags
    applied_to_model = Column(Boolean, default=False, comment="Correction has been used for model training")
    pattern_improvement_suggested = Column(Text, nullable=True, comment="Suggested pattern improvement")

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    extraction = relationship("DocumentExtraction", back_populates="corrections")
    user = relationship("User", foreign_keys=[corrected_by])

    # Indexes
    __table_args__ = (
        Index('ix_correction_field', 'field_name', 'correction_type'),
        Index('ix_correction_user', 'corrected_by', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<ExtractionCorrection(id={self.id}, field='{self.field_name}', type='{self.correction_type}')>"


class TrainingSample(Base):
    """
    Stores training samples collected from extractions.

    Used for model fine-tuning and pattern improvement.
    """

    __tablename__ = "training_samples"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(String(100), unique=True, nullable=False, index=True, comment="Unique sample identifier")

    # Link to extraction
    extraction_id = Column(Integer, ForeignKey("document_extractions.id"), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)

    # Document classification
    document_type = Column(String(50), nullable=False, index=True)

    # Source text
    raw_text = Column(Text, nullable=False, comment="Original OCR text")
    text_hash = Column(String(64), nullable=False, comment="Hash for deduplication")

    # Extracted and ground truth data
    extracted_data = Column(JSON, nullable=False, comment="Extraction result")
    ground_truth = Column(JSON, nullable=True, comment="Verified correct values")

    # Quality metrics
    has_ground_truth = Column(Boolean, default=False, index=True)
    overall_confidence = Column(Float, default=0.0)

    # Training status
    used_for_training = Column(Boolean, default=False, index=True)
    training_batch = Column(String(50), nullable=True, comment="Training batch identifier")
    trained_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    source = Column(String(50), default="extraction", comment="How sample was collected")
    quality_score = Column(Float, default=0.0, comment="Sample quality score for prioritization")

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    extraction = relationship("DocumentExtraction", back_populates="training_samples")
    document = relationship("Document", backref="training_samples")

    # Indexes and constraints
    __table_args__ = (
        Index('ix_sample_type_truth', 'document_type', 'has_ground_truth'),
        Index('ix_sample_training', 'used_for_training', 'quality_score'),
        UniqueConstraint('text_hash', name='uq_training_sample_text'),
    )

    def __repr__(self) -> str:
        return f"<TrainingSample(id={self.id}, sample_id='{self.sample_id}', type='{self.document_type}')>"


class ExtractionAccuracyMetric(Base):
    """
    Aggregated accuracy metrics for extractions.

    Tracks accuracy over time by field, document type, etc.
    """

    __tablename__ = "extraction_accuracy_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # Metric scope
    field_name = Column(String(100), nullable=True, index=True, comment="Field name or 'all' for overall")
    document_type = Column(String(50), nullable=True, index=True, comment="Document type or 'all'")

    # Time period
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False)

    # Metrics
    total_extractions = Column(Integer, default=0)
    total_corrections = Column(Integer, default=0)
    accuracy_rate = Column(Float, default=0.0, comment="(total - corrections) / total")

    # Correction type breakdown
    missing_value_count = Column(Integer, default=0)
    false_positive_count = Column(Integer, default=0)
    wrong_value_count = Column(Integer, default=0)
    formatting_count = Column(Integer, default=0)

    # Confidence distribution
    high_confidence_count = Column(Integer, default=0)
    medium_confidence_count = Column(Integer, default=0)
    low_confidence_count = Column(Integer, default=0)

    # Average confidence when corrected
    avg_confidence_when_corrected = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Indexes
    __table_args__ = (
        Index('ix_metric_scope', 'field_name', 'document_type'),
        Index('ix_metric_period', 'period_start', 'period_end'),
        UniqueConstraint('field_name', 'document_type', 'period_start', name='uq_metric_scope_period'),
    )

    def __repr__(self) -> str:
        return f"<ExtractionAccuracyMetric(field='{self.field_name}', accuracy={self.accuracy_rate:.2%})>"


class ExtractionPattern(Base):
    """
    Stores extraction patterns with performance metrics.

    Tracks which patterns work best for each field type.
    """

    __tablename__ = "extraction_patterns"

    id = Column(Integer, primary_key=True, index=True)

    # Pattern identification
    field_name = Column(String(100), nullable=False, index=True)
    document_type = Column(String(50), nullable=True, index=True)
    pattern_regex = Column(Text, nullable=False)

    # Pattern metadata
    description = Column(Text, nullable=True)
    capture_group = Column(Integer, default=1, comment="Which regex group contains the value")
    requires_cleaning = Column(Boolean, default=False)
    cleaning_function = Column(String(100), nullable=True)

    # Performance metrics
    times_used = Column(Integer, default=0)
    times_correct = Column(Integer, default=0)
    times_corrected = Column(Integer, default=0)
    accuracy_rate = Column(Float, default=0.0)

    # Average confidence when this pattern matches
    avg_confidence = Column(Float, default=0.0)

    # Status
    is_active = Column(Boolean, default=True, index=True)
    priority = Column(Integer, default=0, comment="Higher priority patterns tried first")

    # Source
    source = Column(String(50), default="manual", comment="manual, learned, imported")
    created_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Indexes and constraints
    __table_args__ = (
        Index('ix_pattern_field_type', 'field_name', 'document_type'),
        Index('ix_pattern_active_priority', 'is_active', 'priority'),
        UniqueConstraint('field_name', 'document_type', 'pattern_regex', name='uq_pattern'),
    )

    def __repr__(self) -> str:
        return f"<ExtractionPattern(field='{self.field_name}', accuracy={self.accuracy_rate:.2%})>"

    def record_usage(self, was_correct: bool) -> None:
        """Record pattern usage and update metrics."""
        self.times_used += 1
        if was_correct:
            self.times_correct += 1
        else:
            self.times_corrected += 1

        if self.times_used > 0:
            self.accuracy_rate = self.times_correct / self.times_used
