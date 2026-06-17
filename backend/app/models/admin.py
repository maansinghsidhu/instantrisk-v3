"""
InstantRisk V3 - Admin Panel Models

Audit log of admin actions on the platform (user approvals, tier changes,
deactivations, role changes). This is separate from the (not-yet-implemented)
AIDecisionLog and serves as the human-action audit trail that the admin panel
can display out of the box.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
import uuid as uuid_mod

from app.core.database import Base


class AdminAction(str):
    """String constants for admin action types."""
    USER_APPROVE = "user.approve"
    USER_REJECT = "user.reject"
    USER_DEACTIVATE = "user.deactivate"
    USER_REACTIVATE = "user.reactivate"
    TIER_CHANGE = "user.tier_change"
    ROLE_CHANGE = "user.role_change"
    TWO_FA_RESET = "user.two_fa_reset"


class AdminAuditLog(Base):
    """
    Audit log of admin actions. Written by the admin panel router on every
    privileged action. Read by the admin panel's audit log viewer.

    Note: This is intentionally separate from any future AIDecisionLog
    (which captures AI agent decisions). AdminAuditLog captures human admin
    actions, which is what the W3-19/20 patches do NOT cover.
    """
    __tablename__ = "admin_audit_logs"

    id = Column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid_mod.uuid4,
        index=True,
    )
    admin_id = Column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="The admin user who performed the action",
    )
    target_user_id = Column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
        comment="The user the action was performed on (null for global actions)",
    )
    action = Column(
        String(64),
        nullable=False,
        index=True,
        comment="Action type (see AdminAction constants)",
    )
    details = Column(
        JSONB,
        nullable=True,
        comment="Action-specific structured details (tier changes, etc.)",
    )
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_admin_audit_logs_action_created", "action", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AdminAuditLog(id={self.id}, admin_id={self.admin_id}, "
            f"action='{self.action}', target_user_id={self.target_user_id})>"
        )
