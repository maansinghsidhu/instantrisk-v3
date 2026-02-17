"""
Assessment Vector Model for Precedent Search

Stores embeddings of assessments for semantic similarity search.
"""

from sqlalchemy import Column, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone

from app.models.base import Base


class AssessmentVector(Base):
    """
    Stores vector embeddings of assessments for semantic similarity search.

    Enables "precedent search" - finding similar historical assessments
    to inform current underwriting decisions.
    """
    __tablename__ = "assessment_vectors"

    assessment_id = Column(
        PgUUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        primary_key=True,
        index=True
    )

    # 768-dimensional embedding from sentence-transformers
    embedding = Column(Vector(768), nullable=False)

    # Metadata for filtering (risk_category, territory, decision, etc.)
    metadata = Column(JSONB, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
