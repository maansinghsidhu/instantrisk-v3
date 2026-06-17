"""
InstantRisk V3 - Decision Log Models

Re-introduces the `AIDecisionLog` and `AuditLog` tables that the audit's
W3-19/20 patches require. These were dropped by alembic migration 099 when
the Lloyd's system was removed; the audit's WAVE1 finding D1.1 flagged
that AIDecisionLog had no writers. This module re-adds the tables with
the columns the writer expects (including the `prev_hash` and `input_hash`
chain columns).

These are intentionally separate from `app.models.admin.AdminAuditLog`:
- AdminAuditLog captures HUMAN admin actions (user approvals, tier
  changes) - the admin panel reads it.
- AIDecisionLog + AuditLog capture AI AGENT decisions and a full
  user-action trail - regulatory evidence (NAIC, NYDFS, Lloyd's SR 1-1).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime,
    Float,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
import uuid as uuid_mod

from app.core.database import Base


class AIDecisionLog(Base):
    """A single decision emitted by an AI agent.

    The chain columns (`prev_hash`, `input_hash`) are populated by the
    W3-19 `patches.decision_log_writer.write_ai_decision_log` helper. The
    chain makes the log tamper-evident: any edit to a historical row
    breaks `verify_chain()`.
    """
    __tablename__ = "ai_decision_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Agent / model identification
    agent_name = Column(String(100), nullable=False, index=True)
    agent_version = Column(String(50), nullable=True)
    model_name = Column(String(100), nullable=True)
    decision_type = Column(String(100), nullable=False, index=True)

    # Optional FK to the assessment that triggered the decision. Kept as a
    # soft reference (no hard FK) to avoid coupling the audit log to
    # the assessment lifecycle.
    assessment_id = Column(
        PgUUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Inputs and outputs (PII-redaction is the responsibility of the
    # caller; see patches/pii_redaction.py W3-39).
    input_data = Column(JSONB, default=dict, nullable=False)
    output_data = Column(JSONB, default=dict, nullable=False)
    confidence_score = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    key_factors = Column(JSONB, default=list, nullable=False)

    # Human override fields
    human_override = Column(Boolean, default=False, nullable=False)
    override_by = Column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    override_reason = Column(Text, nullable=True)
    override_at = Column(DateTime(timezone=True), nullable=True)

    # Tamper-evidence chain (populated by decision_log_writer)
    prev_hash = Column(String(64), nullable=True)
    input_hash = Column(String(64), nullable=True)

    # Free-form extras
    extra = Column("extra_data", JSONB, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_ai_decision_logs_agent_timestamp", "agent_name", "timestamp"),
        Index("ix_ai_decision_logs_decision_timestamp", "decision_type", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<AIDecisionLog(id={self.id}, agent='{self.agent_name}', "
            f"decision='{self.decision_type}')>"
        )


class AuditLog(Base):
    """A user-action audit row (the W3-20 patch target).

    Captures user-driven changes to entities (assessment updated, quote
    accepted, document generated, etc.). Distinct from AdminAuditLog,
    which captures admin moderation actions.
    """
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Actor
    user_id = Column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    user_email = Column(String(255), nullable=True)

    # Action
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100), nullable=True, index=True)
    entity_id = Column(String(100), nullable=True, index=True)

    # Diff payload
    old_values = Column(JSONB, default=dict, nullable=False)
    new_values = Column(JSONB, default=dict, nullable=False)

    # Request context
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True)

    # Tamper-evidence chain (populated by decision_log_writer)
    prev_hash = Column(String(64), nullable=True)
    input_hash = Column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_audit_logs_action_timestamp", "action", "timestamp"),
        Index("ix_audit_logs_user_timestamp", "user_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, user_id={self.user_id}, "
            f"action='{self.action}')>"
        )
