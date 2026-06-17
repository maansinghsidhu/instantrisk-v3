"""Add admin audit log table

Revision ID: 105_add_admin_audit_log
Revises: 104_add_event_monitoring
Create Date: 2026-06-17 00:00:00

Adds the `admin_audit_logs` table to capture all human admin actions
(user approvals, rejections, tier changes, deactivations, role changes,
2FA resets). This is the human-action audit trail used by the admin
panel's audit log viewer. It is intentionally separate from any
future AIDecisionLog (which would capture AI agent decisions per
the W3-19/20 patches).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '105_add_admin_audit_log'
down_revision = '104_add_event_monitoring'
branch_labels = None
depends_on = None


def upgrade():
    """Create the admin_audit_logs table."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            admin_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            target_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            action VARCHAR(64) NOT NULL,
            details JSONB,
            ip_address VARCHAR(64),
            user_agent TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_admin_id
        ON admin_audit_logs(admin_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_target_user_id
        ON admin_audit_logs(target_user_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_action
        ON admin_audit_logs(action)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_created_at
        ON admin_audit_logs(created_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_action_created
        ON admin_audit_logs(action, created_at)
    """)

    print("✓ admin_audit_logs table created with 5 indexes")


def downgrade():
    """Drop the admin_audit_logs table and its indexes."""
    op.execute("DROP INDEX IF EXISTS ix_admin_audit_logs_action_created")
    op.execute("DROP INDEX IF EXISTS ix_admin_audit_logs_created_at")
    op.execute("DROP INDEX IF EXISTS ix_admin_audit_logs_action")
    op.execute("DROP INDEX IF EXISTS ix_admin_audit_logs_target_user_id")
    op.execute("DROP INDEX IF EXISTS ix_admin_audit_logs_admin_id")
    op.execute("DROP TABLE IF EXISTS admin_audit_logs CASCADE")
    print("✓ admin_audit_logs table and indexes dropped")
