"""
InstantRisk V2 - Share Link Model

This module defines the ShareLink SQLAlchemy model for creating temporary
shareable links to assessments (24-hour expiry).
"""

from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


def generate_token():
    """Generate a unique share token."""
    return str(uuid.uuid4())


class ShareLink(Base):
    """
    ShareLink model for creating temporary assessment sharing links.

    Attributes:
        id: Primary key identifier.
        assessment_id: Foreign key to the assessment being shared.
        token: Unique UUID token for accessing the shared assessment.
        created_by: User ID who created the share link.
        created_at: When the link was created.
        expires_at: When the link expires (default: 24 hours after creation).
        is_revoked: Whether the link has been manually revoked.
        access_count: Number of times the link has been accessed.
        last_accessed_at: When the link was last accessed.
    """

    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=False, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True, default=generate_token)
    created_by = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    access_count = Column(Integer, default=0, nullable=False)
    last_accessed_at = Column(DateTime, nullable=True)

    # Relationships
    assessment = relationship("Assessment", backref="share_links")
    creator = relationship("User", backref="created_share_links")

    def __init__(self, **kwargs):
        """Initialize with default 24-hour expiry."""
        if 'expires_at' not in kwargs:
            kwargs['expires_at'] = datetime.utcnow() + timedelta(hours=24)
        if 'token' not in kwargs:
            kwargs['token'] = generate_token()
        super().__init__(**kwargs)

    def is_valid(self) -> bool:
        """Check if the share link is still valid (not expired and not revoked)."""
        if self.is_revoked:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True

    def record_access(self):
        """Record that the link was accessed."""
        self.access_count += 1
        self.last_accessed_at = datetime.utcnow()

    def revoke(self):
        """Revoke the share link."""
        self.is_revoked = True
