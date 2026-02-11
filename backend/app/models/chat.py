"""
Chat Models - Database models for AI chat functionality
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ChatMessage(Base):
    """Individual chat message in a conversation."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(String(50), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    extra_data = Column(JSON, default={})  # Store sources, tokens, etc.
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_chat_user_conv", "user_id", "conversation_id"),
        Index("idx_chat_created", "created_at"),
    )


class ChatConversation(Base):
    """Chat conversation metadata."""

    __tablename__ = "chat_conversations"

    id = Column(String(50), primary_key=True)
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=True)
    assessment_id = Column(PgUUID(as_uuid=True), ForeignKey("assessments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extra_data = Column(JSON, default={})


class ChatFeedback(Base):
    """User feedback on AI responses."""

    __tablename__ = "chat_feedback"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False)
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
