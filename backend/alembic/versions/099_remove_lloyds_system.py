"""Remove Lloyd's syndicate system

Revision ID: 099_remove_lloyds
Revises: 002c9bbaa628
Create Date: 2026-02-17 21:30:00

Removes Lloyd's-specific tables and columns as InstantRisk now targets
global underwriters, not Lloyd's market specifically.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '099_remove_lloyds'
down_revision = '002c9bbaa628'
branch_labels = None
depends_on = None


def upgrade():
    """Remove Lloyd's system from database."""

    # Remove syndicate_id foreign key from quotes table (if exists)
    op.execute("ALTER TABLE IF EXISTS quotes DROP CONSTRAINT IF EXISTS quotes_syndicate_id_fkey")
    op.execute("ALTER TABLE IF EXISTS quotes DROP COLUMN IF EXISTS syndicate_id")

    # Remove syndicate_id from users table
    op.execute("ALTER TABLE IF EXISTS users DROP COLUMN IF EXISTS syndicate_id")

    # Remove syndicate_id from assessments table
    op.execute("ALTER TABLE IF EXISTS assessments DROP COLUMN IF EXISTS syndicate_id")

    # Drop Lloyd's-specific tables (in order to avoid FK conflicts)
    # Note: Using IF EXISTS to handle cases where tables don't exist

    # Dependent tables first
    op.execute("DROP TABLE IF EXISTS placement_activity_log CASCADE")
    op.execute("DROP TABLE IF EXISTS syndicate_lines CASCADE")
    op.execute("DROP TABLE IF EXISTS subscription_placements CASCADE")
    op.execute("DROP TABLE IF EXISTS exposure_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS exposure_aggregates CASCADE")
    op.execute("DROP TABLE IF EXISTS event_accumulations CASCADE")
    op.execute("DROP TABLE IF EXISTS data_quality_reports CASCADE")
    op.execute("DROP TABLE IF EXISTS compliance_submissions CASCADE")
    op.execute("DROP TABLE IF EXISTS compliance_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS ai_decision_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS integration_sync_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS integration_connectors CASCADE")
    op.execute("DROP TABLE IF EXISTS unique_market_references CASCADE")

    # Core tables last
    op.execute("DROP TABLE IF EXISTS syndicates CASCADE")

    print("✓ Lloyd's system removed from database")


def downgrade():
    """Restore Lloyd's system (not recommended - use git to restore code first)."""

    # Add syndicate_id back to users
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS syndicate_id INTEGER")

    # Add syndicate_id back to assessments
    op.execute("ALTER TABLE assessments ADD COLUMN IF NOT EXISTS syndicate_id INTEGER")

    # Recreate syndicates table (minimal structure)
    op.execute("""
        CREATE TABLE IF NOT EXISTS syndicates (
            id SERIAL PRIMARY KEY,
            syndicate_number VARCHAR(10) UNIQUE NOT NULL,
            name VARCHAR(200) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Restore foreign keys
    op.execute("""
        ALTER TABLE users
        ADD CONSTRAINT users_syndicate_id_fkey
        FOREIGN KEY (syndicate_id) REFERENCES syndicates(id)
    """)

    op.execute("""
        ALTER TABLE assessments
        ADD CONSTRAINT assessments_syndicate_id_fkey
        FOREIGN KEY (syndicate_id) REFERENCES syndicates(id)
    """)

    print("⚠ Lloyd's columns restored (tables NOT recreated - restore from git)")
