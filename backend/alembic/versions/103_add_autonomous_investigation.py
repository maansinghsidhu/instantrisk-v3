"""Add autonomous investigation columns

Revision ID: 103_add_autonomous_investigation
Revises: 101_add_risk_monitoring
Create Date: 2026-02-18 00:00:00

Adds support for autonomous investigation feature that uses LangGraph
to orchestrate multi-agent company investigations.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '103_add_autonomous_investigation'
down_revision = '101_add_risk_monitoring'
branch_labels = None
depends_on = None


def upgrade():
    """Add investigation_report and investigation_status columns to assessments."""

    # Add investigation_report JSONB column to store full investigation results
    op.execute("""
        ALTER TABLE assessments
        ADD COLUMN IF NOT EXISTS investigation_report JSONB DEFAULT '{}'
    """)

    # Add investigation_status VARCHAR column to track investigation progress
    # Possible values: not_started, in_progress, completed, failed
    op.execute("""
        ALTER TABLE assessments
        ADD COLUMN IF NOT EXISTS investigation_status VARCHAR(20) DEFAULT 'not_started'
    """)

    # Create index on investigation_status for filtering
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_assessments_investigation_status
        ON assessments(investigation_status)
    """)

    # Create GIN index on investigation_report for JSON querying
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_assessments_investigation_report
        ON assessments USING gin (investigation_report)
    """)

    print("✓ Autonomous investigation columns added to assessments table")


def downgrade():
    """Remove autonomous investigation columns."""

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_assessments_investigation_report")
    op.execute("DROP INDEX IF EXISTS idx_assessments_investigation_status")

    # Drop columns
    op.execute("ALTER TABLE assessments DROP COLUMN IF EXISTS investigation_status")
    op.execute("ALTER TABLE assessments DROP COLUMN IF EXISTS investigation_report")

    print("✓ Autonomous investigation columns removed")
