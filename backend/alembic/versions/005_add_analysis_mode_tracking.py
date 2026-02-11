"""Add analysis mode tracking columns to assessments

Revision ID: 005_analysis_mode
Revises: 004_extraction
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_analysis_mode'
down_revision = '003_rbac_teams'
branch_labels = None
depends_on = None


def upgrade():
    """Add analysis_mode and previous_analysis_json columns to assessments."""

    # Add analysis_mode column
    op.add_column(
        'assessments',
        sa.Column(
            'analysis_mode',
            sa.String(20),
            nullable=True,
            comment='Analysis depth: quick/go_no_go/deep'
        )
    )

    # Add previous_analysis_json column
    op.add_column(
        'assessments',
        sa.Column(
            'previous_analysis_json',
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            comment='Prior analysis results if upgraded from lower mode'
        )
    )

    # Create index on analysis_mode for filtering
    op.create_index(
        'ix_assessments_analysis_mode',
        'assessments',
        ['analysis_mode']
    )


def downgrade():
    """Remove analysis_mode and previous_analysis_json columns."""
    op.drop_index('ix_assessments_analysis_mode', table_name='assessments')
    op.drop_column('assessments', 'previous_analysis_json')
    op.drop_column('assessments', 'analysis_mode')
