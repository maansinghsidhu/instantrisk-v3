"""
InstantRisk V2 - Submission Share Model

This module defines the SubmissionShare SQLAlchemy model for sharing
submissions/assessments between internal users.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.core.database import Base


class ShareType(str, enum.Enum):
    ORIGINALS = "originals"
    ANALYSIS = "analysis"


class SubmissionShare(Base):
    """
    SubmissionShare model for internal sharing between users.

    Attributes:
        id: Primary key identifier.
        assessment_id: Foreign key to the assessment being shared.
        shared_by: User ID who created the share.
        shared_with: User ID who received the share.
        share_type: Type of share - "originals" (documents) or "analysis" (AI results).
        include_documents: Whether to include the original documents.
        message: Optional message from the sharer.
        created_at: When the share was created.
        is_revoked: Whether the share has been revoked.
    """

    __tablename__ = "submission_shares"

    id = Column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(
        PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False, index=True
    )
    shared_by = Column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    shared_with = Column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    share_type = Column(SQLEnum(ShareType), nullable=False, default=ShareType.ANALYSIS)
    include_documents = Column(Boolean, default=True, nullable=False)
    message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    assessment = relationship("Assessment", backref="submission_shares")
    sharer = relationship("User", foreign_keys=[shared_by], backref="sent_shares")
    recipient = relationship(
        "User", foreign_keys=[shared_with], backref="received_shares"
    )

    def revoke(self):
        """Revoke the share."""
        self.is_revoked = True
