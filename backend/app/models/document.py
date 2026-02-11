"""
InstantRisk V2 - Document Model

This module defines the Document SQLAlchemy model for tracking
uploaded documents and their OCR processing status.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    """Enumeration of document processing statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, enum.Enum):
    """Enumeration of supported document types."""
    SLIP = "slip"
    POLICY = "policy"
    ENDORSEMENT = "endorsement"
    CLAIM = "claim"
    SURVEY_REPORT = "survey_report"
    FINANCIAL_STATEMENT = "financial_statement"
    OTHER = "other"


class Document(Base):
    """
    Document model for tracking uploaded documents.

    Attributes:
        id: Primary key identifier.
        filename: Original filename of the uploaded document.
        file_path: Path to the file in object storage (MinIO).
        file_size: Size of the file in bytes.
        mime_type: MIME type of the document.
        document_type: Type of insurance document.
        status: Current processing status.
        uploaded_by: Foreign key to the user who uploaded the document.
        assessment_id: Foreign key to the related assessment.
        ocr_text: Extracted text from OCR processing.
        ocr_confidence: OCR confidence score (0.0 to 1.0).
        ocr_language: Detected or specified language for OCR.
        extracted_data: JSON field containing structured extracted data.
        vector_id: ID in Qdrant vector database for similarity search.
        checksum: MD5 or SHA256 checksum for integrity verification.
        error_message: Error message if processing failed.
        created_at: Timestamp when the document was uploaded.
        updated_at: Timestamp when the document was last updated.
        processed_at: Timestamp when OCR processing completed.
    """

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False, comment="File size in bytes")
    mime_type = Column(String(100), nullable=True)

    # Document classification
    document_type = Column(
        Enum(DocumentType, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=DocumentType.OTHER,
        nullable=False
    )

    # Processing status
    status = Column(
        Enum(DocumentStatus, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True
    )

    # Relationships
    uploaded_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # assessment_id is UUID to match EC2 database schema
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=True)

    # OCR results
    ocr_text = Column(Text, nullable=True)
    ocr_confidence = Column(Integer, nullable=True, comment="OCR confidence score 0-100")
    ocr_language = Column(String(10), default="en", nullable=True)

    # Extracted structured data
    extracted_data = Column(
        JSON,
        default=dict,
        comment="Structured data extracted from document"
    )

    # Vector storage reference
    vector_id = Column(String(255), nullable=True, comment="Vector ID in Qdrant")

    # Integrity
    checksum = Column(String(64), nullable=True, comment="SHA256 checksum")

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
    uploaded_by_user = relationship("User", back_populates="documents")
    assessment = relationship("Assessment", back_populates="documents")
    extractions = relationship("DocumentExtraction", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation of the Document."""
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}')>"

    def mark_processing(self) -> None:
        """Mark the document as currently being processed."""
        self.status = DocumentStatus.PROCESSING

    def mark_completed(self, ocr_text: str, confidence: int) -> None:
        """
        Mark the document processing as completed.

        Args:
            ocr_text: The extracted text from OCR.
            confidence: The OCR confidence score (0-100).
        """
        self.status = DocumentStatus.COMPLETED
        self.ocr_text = ocr_text
        self.ocr_confidence = confidence
        self.processed_at = datetime.now(timezone.utc)
        self.error_message = None

    def mark_failed(self, error_message: str) -> None:
        """
        Mark the document processing as failed.

        Args:
            error_message: Description of the failure.
        """
        self.status = DocumentStatus.FAILED
        self.error_message = error_message
        self.processed_at = datetime.now(timezone.utc)
