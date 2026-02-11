"""
InstantRisk V2 - Template Models

This module defines the Template and TemplateFavorite SQLAlchemy models
for managing document templates (both system and user-created).
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class TemplateCategory(str, enum.Enum):
    """Enumeration of template categories."""
    LLOYDS = "lloyds"
    COMMERCIAL = "commercial"
    SPECIALTY = "specialty"
    CUSTOM = "custom"


class TemplateDocumentType(str, enum.Enum):
    """Enumeration of template document types."""
    SLIP = "slip"
    POLICY = "policy"
    CERTIFICATE = "certificate"
    ENDORSEMENT = "endorsement"
    SCHEDULE = "schedule"
    PLAN = "plan"
    AGREEMENT = "agreement"
    OTHER = "other"


class Template(Base):
    """
    Template model for managing document templates.

    Attributes:
        id: Primary key identifier.
        template_key: Unique key for the template (e.g., "lloyds_mrc_slip").
        name: Display name of the template.
        description: Detailed description of the template purpose.
        category: Category (lloyds, commercial, specialty, custom).
        document_type: Type of document this template generates.
        is_system: Whether this is a preloaded system template.
        created_by: Foreign key to the user who created the template (null for system).
        fields: JSON field definitions for dynamic form generation.
        sections: JSON sections structure for the document.
        sample_data: JSON sample data for previews.
        master_file_path: Optional path to master template file in MinIO.
        is_active: Whether the template is active.
        is_public: Whether visible to all users (for shared templates).
        tags: Array of searchable tags.
        use_count: Number of times the template has been used.
        created_at: Timestamp when created.
        updated_at: Timestamp when last updated.
    """

    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    template_key = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(20), default="1.0")

    # Classification
    category = Column(String(50), nullable=False, default="custom", index=True)
    document_type = Column(String(50), nullable=False, default="other")

    # Source
    is_system = Column(Boolean, default=False, index=True)
    created_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Content - using JSONB for PostgreSQL performance
    fields = Column(JSONB, nullable=False, default=dict)
    sections = Column(JSONB, default=list)
    sample_data = Column(JSONB, default=dict)

    # Optional master file
    master_file_path = Column(String(512), nullable=True)
    master_file_type = Column(String(50), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_public = Column(Boolean, default=False)

    # Metadata
    tags = Column(ARRAY(String), default=list)
    use_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    created_by_user = relationship("User", back_populates="templates")
    favorites = relationship("TemplateFavorite", back_populates="template", cascade="all, delete-orphan")
    generated_documents = relationship("GeneratedDocument", back_populates="template")

    def __repr__(self) -> str:
        return f"<Template(id={self.id}, key='{self.template_key}', name='{self.name}')>"

    def increment_use_count(self) -> None:
        """Increment the template usage counter."""
        self.use_count = (self.use_count or 0) + 1


class TemplateFavorite(Base):
    """
    TemplateFavorite model for tracking user's favorite templates.

    Attributes:
        id: Primary key identifier.
        user_id: Foreign key to the user.
        template_id: Foreign key to the template.
        created_at: Timestamp when favorited.
    """

    __tablename__ = "template_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="template_favorites")
    template = relationship("Template", back_populates="favorites")

    # Unique constraint
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

    def __repr__(self) -> str:
        return f"<TemplateFavorite(user_id={self.user_id}, template_id={self.template_id})>"
