"""Add users.is_super_admin (Fix #14: admin-on-admin DoS)

Revision ID: 108_add_is_super_admin
Revises: 107_add_token_invalidated_at
Create Date: 2026-06-17 00:00:00

Adds the `is_super_admin` flag to users. Only a super admin can
deactivate another admin. Without this, any compromised admin can
lock out every other admin (DoS).

To bootstrap: after deploy, run
    UPDATE users SET is_super_admin = TRUE WHERE email = '<owner>';
"""
from alembic import op


revision = '108_add_is_super_admin'
down_revision = '107_add_token_invalidated_at'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_super_admin BOOLEAN NOT NULL DEFAULT FALSE
    """)
    print("OK: users.is_super_admin added (default FALSE; bootstrap manually)")


def downgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_super_admin")
    print("OK: users.is_super_admin dropped")
