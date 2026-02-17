"""Add global event monitoring table

Revision ID: 104_add_event_monitoring
Revises: 103_add_autonomous_investigation
Create Date: 2026-02-18 00:00:00

Adds the global_events table for tracking 24/7 real-time events
from GDELT, USGS, NOAA, NASA FIRMS, and CISA that may affect
the portfolio of insured assessments.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '104_add_event_monitoring'
down_revision = '103_add_autonomous_investigation'
branch_labels = None
depends_on = None


def upgrade():
    """Create global_events table and supporting indexes."""

    op.execute("""
        CREATE TABLE IF NOT EXISTS global_events (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(50) NOT NULL,
            source VARCHAR(50) NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            severity VARCHAR(20) NOT NULL DEFAULT 'low',
            location VARCHAR(255),
            lat DOUBLE PRECISION,
            lon DOUBLE PRECISION,
            affected_region VARCHAR(255),
            raw_data JSONB DEFAULT '{}',
            event_time TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            is_processed BOOLEAN DEFAULT FALSE NOT NULL,
            affected_assessment_count INTEGER DEFAULT 0
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_global_events_event_type
        ON global_events(event_type)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_global_events_severity
        ON global_events(severity)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_global_events_event_time
        ON global_events(event_time DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_global_events_source
        ON global_events(source)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_global_events_location
        ON global_events(location)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_global_events_raw_data
        ON global_events USING gin (raw_data)
    """)

    print("global_events table and indexes created")


def downgrade():
    """Drop global_events table."""
    op.execute("DROP INDEX IF EXISTS idx_global_events_raw_data")
    op.execute("DROP INDEX IF EXISTS idx_global_events_location")
    op.execute("DROP INDEX IF EXISTS idx_global_events_source")
    op.execute("DROP INDEX IF EXISTS idx_global_events_event_time")
    op.execute("DROP INDEX IF EXISTS idx_global_events_severity")
    op.execute("DROP INDEX IF EXISTS idx_global_events_event_type")
    op.execute("DROP TABLE IF EXISTS global_events")
    print("global_events table dropped")
