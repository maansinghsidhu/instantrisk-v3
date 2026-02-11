"""subscription and approval

Revision ID: 006_subscription_approval
Revises: 004_extraction, 005_analysis_mode (merge)
Create Date: 2026-02-01

This migration adds:
1. Subscription table for tiered access (Basic/Premium)
2. Approval fields to users table for admin approval workflow
3. Migrates existing users to approved status with Premium tier (1 year bonus)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime, timezone, timedelta


# revision identifiers, used by Alembic.
revision = '006_subscription_approval'
down_revision = ('004_extraction', '005_analysis_mode')  # Multiple heads merge
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create approval_status enum type
    approval_status_enum = postgresql.ENUM('pending', 'approved', 'rejected', name='approvalstatus', create_type=False)
    approval_status_enum.create(op.get_bind(), checkfirst=True)

    # Create subscription_tier enum type
    subscription_tier_enum = postgresql.ENUM('trial', 'basic', 'premium', name='subscriptiontier', create_type=False)
    subscription_tier_enum.create(op.get_bind(), checkfirst=True)

    # Create subscription_status enum type
    subscription_status_enum = postgresql.ENUM('pending', 'active', 'expired', 'cancelled', name='subscriptionstatus', create_type=False)
    subscription_status_enum.create(op.get_bind(), checkfirst=True)

    # Add approval columns to users table
    op.add_column('users', sa.Column('approval_status',
        sa.Enum('pending', 'approved', 'rejected', name='approvalstatus'),
        server_default='approved',  # Existing users auto-approved
        nullable=False
    ))
    op.add_column('users', sa.Column('approved_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('users', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('rejection_reason', sa.Text(), nullable=True))

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), unique=True, nullable=False),
        sa.Column('tier', sa.Enum('trial', 'basic', 'premium', name='subscriptiontier'), nullable=False, server_default='trial'),
        sa.Column('status', sa.Enum('pending', 'active', 'expired', 'cancelled', name='subscriptionstatus'), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('monthly_assessments_used', sa.Integer(), server_default='0'),
        sa.Column('monthly_documents_generated', sa.Integer(), server_default='0'),
        sa.Column('monthly_chat_messages_used', sa.Integer(), server_default='0'),
        sa.Column('usage_reset_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indexes
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_index('ix_subscriptions_tier', 'subscriptions', ['tier'])
    op.create_index('ix_subscriptions_status', 'subscriptions', ['status'])
    op.create_index('ix_users_approval_status', 'users', ['approval_status'])

    # Migrate existing users: set approved_at for auto-approved users
    op.execute("""
        UPDATE users
        SET approved_at = NOW()
        WHERE approval_status = 'approved' AND approved_at IS NULL
    """)

    # Create Premium subscriptions for all existing users (migration bonus)
    # This gives existing users 1 year of Premium access
    op.execute("""
        INSERT INTO subscriptions (user_id, tier, status, started_at, expires_at, created_at, updated_at)
        SELECT
            id,
            'premium',
            'active',
            NOW(),
            NOW() + INTERVAL '1 year',
            NOW(),
            NOW()
        FROM users
        WHERE id NOT IN (SELECT user_id FROM subscriptions WHERE user_id IS NOT NULL)
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_users_approval_status', table_name='users')
    op.drop_index('ix_subscriptions_status', table_name='subscriptions')
    op.drop_index('ix_subscriptions_tier', table_name='subscriptions')
    op.drop_index('ix_subscriptions_user_id', table_name='subscriptions')

    # Drop subscriptions table
    op.drop_table('subscriptions')

    # Remove approval columns from users
    op.drop_column('users', 'rejection_reason')
    op.drop_column('users', 'approved_at')
    op.drop_column('users', 'approved_by')
    op.drop_column('users', 'approval_status')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS subscriptionstatus')
    op.execute('DROP TYPE IF EXISTS subscriptiontier')
    op.execute('DROP TYPE IF EXISTS approvalstatus')
