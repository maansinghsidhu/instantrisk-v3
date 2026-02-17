"""Add risk monitoring alerts

Revision ID: 101_add_risk_monitoring
Revises: 100_add_precedent_search
Create Date: 2026-02-17 23:55:00

Enables continuous 24/7 monitoring of risk factors.
"""
from alembic import op
import sqlalchemy as sa

revision = '101_add_risk_monitoring'
down_revision = '100_add_precedent_search'
branch_labels = None
depends_on = None


def upgrade():
    """Create risk_monitoring_alerts table."""

    op.execute("""
        CREATE TABLE IF NOT EXISTS risk_monitoring_alerts (
            id SERIAL PRIMARY KEY,
            assessment_id UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
            alert_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            message TEXT NOT NULL,
            details JSONB DEFAULT '{}',
            source VARCHAR(100) NOT NULL,
            source_url TEXT,
            acknowledged BOOLEAN DEFAULT FALSE,
            acknowledged_by UUID REFERENCES users(id),
            acknowledged_at TIMESTAMP WITH TIME ZONE,
            detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_assessment ON risk_monitoring_alerts(assessment_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_type ON risk_monitoring_alerts(alert_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_severity ON risk_monitoring_alerts(severity)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON risk_monitoring_alerts(acknowledged)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_detected_at ON risk_monitoring_alerts(detected_at)")

    print("✓ Risk monitoring alerts table created")


def downgrade():
    """Remove risk monitoring table."""
    op.execute("DROP TABLE IF EXISTS risk_monitoring_alerts CASCADE")
    print("✓ Risk monitoring table removed")
