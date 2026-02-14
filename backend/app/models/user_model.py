"""
User Model Adapter — tracks per-user ML adapter training status.

Each user who uploads enough training documents (50+ chunks) can have
a personalized adapter trained on top of the base InsuranceMultiTaskModel.
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
from datetime import datetime, timezone

from app.core.database import Base


class UserModelAdapter(Base):
    __tablename__ = "user_model_adapters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(PgUUID(as_uuid=True), nullable=False, index=True, unique=True)
    status = Column(String(20), nullable=False, default="pending")
    # Status values: pending, training, ready, failed, stale
    training_samples = Column(Integer, default=0)
    training_chunks = Column(Integer, default=0)
    adapter_path = Column(String(500))  # Local or S3 path
    base_model_version = Column(String(100), default="instantrisk-engine-v1")
    accuracy_clause = Column(Float)
    accuracy_appetite = Column(Float)
    accuracy_pricing = Column(Float)
    accuracy_intent = Column(Float)
    training_loss = Column(Float)
    training_config = Column(JSONB)
    error_message = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    trained_at = Column(DateTime)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
