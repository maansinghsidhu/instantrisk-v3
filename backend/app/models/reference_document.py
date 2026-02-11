"""
InstantRisk V2 - Reference Document Model

This module defines the ReferenceDocument SQLAlchemy model for managing
training and reference documents used for RAG-enhanced document generation.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class ReferenceDocCategory(str, enum.Enum):
    """Enumeration of reference document categories."""
    POLICY_WORDING = "policy_wording"
    GUIDELINES = "guidelines"
    PREVIOUS_CONTRACTS = "previous_contracts"
    MARKET_DATA = "market_data"
    REGULATORY = "regulatory"
    CLAUSES = "clauses"
    ENDORSEMENTS = "endorsements"
    OTHER = "other"


class ReferenceDocStatus(str, enum.Enum):
    """Enumeration of reference document processing statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    VECTORIZED = "vectorized"
    FAILED = "failed"


class ReferenceDocument(Base):
    """
    ReferenceDocument model for managing training/reference documents.

    These documents are used to enhance AI document generation through
    RAG (Retrieval Augmented Generation). They are vectorized and stored
    in Qdrant for semantic search.

    Attributes:
        id: Primary key identifier.
        title: Title/name of the reference document.
        description: Detailed description of the document content.
        category: Category of the document.
        uploaded_by: Foreign key to the user who uploaded.
        syndicate_id: Optional foreign key for syndicate-specific docs.
        file_path: Path in MinIO storage.
        file_name: Original filename.
        file_size: Size in bytes.
        mime_type: MIME type of the document.
        ocr_text: Extracted text content.
        content_hash: SHA256 hash for deduplication.
        vector_ids: Array of Qdrant vector IDs (one per chunk).
        embedding_model: Name of the embedding model used.
        chunk_count: Number of text chunks created.
        tags: Array of searchable tags.
        risk_categories: Array of relevant risk categories.
        effective_date: When the document became effective.
        expiry_date: When the document expires.
        jurisdiction: Applicable jurisdiction.
        is_active: Whether the document is active.
        is_verified: Whether admin has verified quality.
        quality_score: OCR quality score (0-1).
        retrieval_count: Number of times retrieved for RAG.
        last_retrieved_at: Last retrieval timestamp.
        created_at: When uploaded.
        processed_at: When vectorization completed.
    """

    __tablename__ = "reference_documents"

    id = Column(Integer, primary_key=True, index=True)

    # Identity
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Classification
    category = Column(String(100), nullable=False, default="other", index=True)
    status = Column(String(50), default="pending", index=True)

    # Source & Ownership
    uploaded_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=True, index=True)

    # File Storage
    file_path = Column(String(512), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=True)

    # Content Processing
    ocr_text = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True, comment="SHA256 for deduplication")

    # Vector Storage (RAG)
    vector_ids = Column(ARRAY(String), default=list, comment="Qdrant vector IDs per chunk")
    embedding_model = Column(String(100), nullable=True)
    chunk_count = Column(Integer, default=0)

    # Metadata for AI
    tags = Column(ARRAY(String), default=list)
    risk_categories = Column(ARRAY(String), default=list, comment="property, cyber, marine, etc.")
    effective_date = Column(DateTime(timezone=True), nullable=True)
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    jurisdiction = Column(String(100), nullable=True)

    # Quality & Status
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False, comment="Admin verified quality")
    quality_score = Column(Float, nullable=True, comment="OCR quality 0-1")

    # Usage tracking
    retrieval_count = Column(Integer, default=0)
    last_retrieved_at = Column(DateTime(timezone=True), nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    uploaded_by_user = relationship("User", back_populates="reference_documents")
    syndicate = relationship("Syndicate", back_populates="reference_documents")

    def __repr__(self) -> str:
        return f"<ReferenceDocument(id={self.id}, title='{self.title}', status='{self.status}')>"

    def mark_processing(self) -> None:
        """Mark the document as currently being processed."""
        self.status = ReferenceDocStatus.PROCESSING.value

    def mark_vectorized(self, vector_ids: list, chunk_count: int) -> None:
        """Mark the document as successfully vectorized."""
        self.status = ReferenceDocStatus.VECTORIZED.value
        self.vector_ids = vector_ids
        self.chunk_count = chunk_count
        self.processed_at = datetime.now(timezone.utc)
        self.error_message = None

    def mark_failed(self, error_message: str) -> None:
        """Mark the document processing as failed."""
        self.status = ReferenceDocStatus.FAILED.value
        self.error_message = error_message
        self.processed_at = datetime.now(timezone.utc)

    def record_retrieval(self) -> None:
        """Record a retrieval event for analytics."""
        self.retrieval_count = (self.retrieval_count or 0) + 1
        self.last_retrieved_at = datetime.now(timezone.utc)
