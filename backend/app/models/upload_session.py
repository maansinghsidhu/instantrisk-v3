"""Upload Session Model"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base

class UploadSession(Base):
    __tablename__ = "upload_sessions"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=True)  # Link to created assessment
    status = Column(String(20), default="waiting")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    documents_json = Column(Text, default="[]")
    analysis_json = Column(Text, nullable=True)  # AI analysis results
    user = relationship("User", back_populates="upload_sessions")
    assessment = relationship("Assessment", back_populates="upload_session")

    @staticmethod
    def generate_token(): return uuid.uuid4().hex

    @staticmethod
    def get_expiry(minutes=30): return datetime.now(timezone.utc) + timedelta(minutes=minutes)
