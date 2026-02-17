"""Add precedent search - assessment vectors

Revision ID: 100_add_precedent_search
Revises: 099_remove_lloyds
Create Date: 2026-02-17 23:50:00

Enables semantic search across all historical assessments to find similar risks.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '100_add_precedent_search'
down_revision = '099_remove_lloyds'
branch_labels = None
depends_on = None


def upgrade():
    """Add assessment_vectors table for precedent search."""

    # Create table
    op.execute("""
        CREATE TABLE IF NOT EXISTS assessment_vectors (
            assessment_id UUID PRIMARY KEY REFERENCES assessments(id) ON DELETE CASCADE,
            embedding vector(768),
            vector_metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Create index for fast cosine similarity search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_assessment_vectors_embedding
        ON assessment_vectors USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # Create metadata index for filtering
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_assessment_vectors_metadata
        ON assessment_vectors USING gin (vector_metadata)
    """)

    print("✓ Precedent search table created")


def downgrade():
    """Remove precedent search table."""
    op.execute("DROP TABLE IF EXISTS assessment_vectors CASCADE")
    print("✓ Precedent search table removed")
