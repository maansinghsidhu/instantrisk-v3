"""add share_links table

Revision ID: 007_share_links
Revises: 006_subscription_approval
Create Date: 2026-02-02

This migration adds the share_links table for temporary shareable links
to assessments. Links expire after 24 hours by default.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_share_links'
down_revision = '006_subscription_approval'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create share_links table
    op.create_table(
        'share_links',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('assessment_id', sa.Integer(), sa.ForeignKey('assessments.id'), nullable=False, index=True),
        sa.Column('token', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
    )

    # Create indexes for common queries
    op.create_index('ix_share_links_created_by', 'share_links', ['created_by'])
    op.create_index('ix_share_links_expires_at', 'share_links', ['expires_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_share_links_expires_at', table_name='share_links')
    op.drop_index('ix_share_links_created_by', table_name='share_links')

    # Drop table
    op.drop_table('share_links')
