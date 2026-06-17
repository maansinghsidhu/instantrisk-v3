"""Add users.token_invalidated_at (W3-08 / pr-agent fix #2)

Revision ID: 107_add_token_invalidated_at
Revises: 106_re_add_decision_logs
Create Date: 2026-06-17 00:00:00

Adds the `users.token_invalidated_at` column used to invalidate outstanding
JWTs without waiting for natural expiry. The admin panel sets this on
`deactivate_user`; the reactivation flow clears it. `get_current_user`
rejects any token whose `iat` is before this value.
"""
from alembic import op
import sqlalchemy as sa


revision = '107_add_token_invalidated_at'
down_revision = '106_re_add_decision_logs'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS token_invalidated_at TIMESTAMP WITH TIME ZONE
    """)
    print("OK: users.token_invalidated_at added")


def downgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS token_invalidated_at")
    print("OK: users.token_invalidated_at dropped")
