"""
InstantRisk V2 - Generated Document Models

This module defines the GeneratedDocument and DocumentGenerationJob
SQLAlchemy models for tracking AI-generated documents from assessments.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class GeneratedDocStatus(str, enum.Enum):
    """Enumeration of generated document statuses."""
    PENDING = "pending"
    GENERATING = "generating"
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    FINALIZED = "finalized"
    FAILED = "failed"


class GenerationJobStatus(str, enum.Enum):
    """Enumeration of generation job statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class DocumentGenerationJob(Base):
    """
    DocumentGenerationJob model for tracking batch document generation.

    When a user triggers document generation from an assessment, a job
    is created to track progress across all documents being generated.

    Attributes:
        id: UUID primary key.
        assessment_id: Foreign key to the assessment.
        status: Current job status.
        total_documents: Number of documents to generate.
        completed_documents: Number of documents completed.
        current_agent: Name of the current agent processing.
        progress_percentage: Overall progress (0-100).
        agent_outputs: JSON outputs from each agent.
        error_message: Error message if failed.
        started_at: When processing started.
        completed_at: When processing completed.
    """

    __tablename__ = "document_generation_jobs"

    id = Column(String(50), primary_key=True)  # UUID
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False, index=True)

    # Status tracking
    status = Column(String(20), nullable=False, default="pending", index=True)
    total_documents = Column(Integer, nullable=True)
    completed_documents = Column(Integer, default=0)
    current_agent = Column(String(50), nullable=True)
    current_agent_description = Column(String(255), nullable=True)
    progress_percentage = Column(Integer, default=0)

    # Agent results
    agent_outputs = Column(JSONB, default=dict)
    document_suggestions = Column(JSONB, default=list, comment="AI-suggested documents")

    # Error handling
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    assessment = relationship("Assessment", back_populates="generation_jobs")
    generated_documents = relationship("GeneratedDocument", back_populates="generation_job", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<DocumentGenerationJob(id='{self.id}', status='{self.status}', progress={self.progress_percentage}%)>"

    def start_processing(self) -> None:
        """Mark the job as started."""
        self.status = GenerationJobStatus.PROCESSING.value
        self.started_at = datetime.now(timezone.utc)

    def update_progress(self, agent: str, description: str, percentage: int) -> None:
        """Update job progress."""
        self.current_agent = agent
        self.current_agent_description = description
        self.progress_percentage = percentage

    def complete(self) -> None:
        """Mark the job as completed."""
        self.status = GenerationJobStatus.COMPLETED.value
        self.completed_at = datetime.now(timezone.utc)
        self.progress_percentage = 100
        self.current_agent = None

    def fail(self, error_message: str) -> None:
        """Mark the job as failed."""
        self.status = GenerationJobStatus.FAILED.value
        self.error_message = error_message
        self.completed_at = datetime.now(timezone.utc)


class GeneratedDocument(Base):
    """
    GeneratedDocument model for tracking individual generated documents.

    Each document generated from an assessment is tracked here with
    its draft content, approval status, and final PDF.

    Attributes:
        id: Primary key identifier.
        assessment_id: Foreign key to the assessment.
        generation_job_id: Foreign key to the generation job.
        template_id: Foreign key to the template used.
        document_type: Type of document generated.
        title: Document title.
        version: Version number.
        status: Current document status.
        draft_content: JSON draft content from AI.
        final_content: JSON final content after edits.
        data_mappings: JSON field mappings used.
        ai_suggestions: JSON AI-suggested values.
        compliance_report: JSON compliance check results.
        placeholders_remaining: Count of unfilled placeholders.
        ai_confidence: AI confidence score for the generation.
        pdf_path: Path to generated PDF in MinIO.
        pdf_file_name: Filename of the PDF.
        generation_method: How it was generated (ai_prefill, manual, hybrid).
        reviewed_by: User who reviewed.
        reviewed_at: When reviewed.
        approved_by: User who approved.
        approved_at: When approved.
        created_at: When created.
        finalized_at: When finalized.
    """

    __tablename__ = "generated_documents"

    id = Column(Integer, primary_key=True, index=True)

    # Relationships
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False, index=True)
    generation_job_id = Column(String(50), ForeignKey("document_generation_jobs.id"), nullable=True, index=True)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)

    # Document Info
    document_type = Column(String(50), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    version = Column(Integer, default=1)

    # Status
    status = Column(String(50), default="draft", index=True)

    # Content
    draft_content = Column(JSONB, default=dict, comment="AI-generated draft")
    final_content = Column(JSONB, default=dict, comment="After user edits")
    data_mappings = Column(JSONB, default=dict, comment="Field mappings used")
    ai_suggestions = Column(JSONB, default=dict, comment="AI-recommended values")
    compliance_report = Column(JSONB, default=dict, comment="Compliance check results")

    # Quality metrics
    placeholders_remaining = Column(Integer, default=0)
    ai_confidence = Column(Float, nullable=True, comment="AI confidence 0-1")

    # Generated file
    pdf_path = Column(String(512), nullable=True)
    pdf_file_name = Column(String(255), nullable=True)
    pdf_file_size = Column(Integer, nullable=True)

    # Generation metadata
    generation_method = Column(String(50), default="ai_prefill", comment="ai_prefill, manual, hybrid")

    # Approval workflow
    reviewed_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    finalized_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    assessment = relationship("Assessment", back_populates="generated_documents")
    generation_job = relationship("DocumentGenerationJob", back_populates="generated_documents")
    template = relationship("Template", back_populates="generated_documents")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    approver = relationship("User", foreign_keys=[approved_by])

    def __repr__(self) -> str:
        return f"<GeneratedDocument(id={self.id}, type='{self.document_type}', status='{self.status}')>"

    def mark_generating(self) -> None:
        """Mark the document as currently being generated."""
        self.status = GeneratedDocStatus.GENERATING.value

    def mark_draft(self, content: dict, mappings: dict, confidence: float) -> None:
        """Mark the document as a completed draft."""
        self.status = GeneratedDocStatus.DRAFT.value
        self.draft_content = content
        self.data_mappings = mappings
        self.ai_confidence = confidence
        # Count placeholders
        self._count_placeholders(content)

    def mark_review_required(self, compliance_report: dict) -> None:
        """Mark the document as requiring review."""
        self.status = GeneratedDocStatus.REVIEW_REQUIRED.value
        self.compliance_report = compliance_report

    def mark_approved(self, user_id: str, final_content: dict = None) -> None:
        """Mark the document as approved."""
        self.status = GeneratedDocStatus.APPROVED.value
        self.approved_by = user_id
        self.approved_at = datetime.now(timezone.utc)
        if final_content:
            self.final_content = final_content

    def mark_finalized(self, pdf_path: str, file_name: str, file_size: int) -> None:
        """Mark the document as finalized with PDF."""
        self.status = GeneratedDocStatus.FINALIZED.value
        self.pdf_path = pdf_path
        self.pdf_file_name = file_name
        self.pdf_file_size = file_size
        self.finalized_at = datetime.now(timezone.utc)

    def mark_failed(self, error_message: str) -> None:
        """Mark the document generation as failed."""
        self.status = GeneratedDocStatus.FAILED.value
        self.error_message = error_message

    def _count_placeholders(self, content: dict) -> None:
        """Count remaining placeholders in content."""
        import json
        content_str = json.dumps(content)
        # Count patterns like [PLACEHOLDER] or {placeholder}
        import re
        placeholders = len(re.findall(r'\[[\w_]+\]|\{[\w_]+\}', content_str))
        self.placeholders_remaining = placeholders
