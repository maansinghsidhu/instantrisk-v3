"""Re-add ai_decision_logs and audit_logs (W3-19/W3-20)

Revision ID: 106_re_add_decision_logs
Revises: 105_add_admin_audit_log
Create Date: 2026-06-17 00:00:00

Re-introduces the `ai_decision_logs` and `audit_logs` tables that were
dropped by alembic migration 099 (remove Lloyd's system). The W3-19/20
audit patches (decision_log_writer) write to these tables with hash-chained
tamper-evidence (`prev_hash`, `input_hash`).

This migration is a no-op if the tables already exist (it uses
`CREATE TABLE IF NOT EXISTS`) so it is safe to run in environments where
the tables have been re-created manually.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '106_re_add_decision_logs'
down_revision = '105_add_admin_audit_log'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_decision_logs (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            agent_name VARCHAR(100) NOT NULL,
            agent_version VARCHAR(50),
            model_name VARCHAR(100),
            decision_type VARCHAR(100) NOT NULL,
            assessment_id UUID,
            input_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            output_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            confidence_score DOUBLE PRECISION,
            reasoning TEXT,
            key_factors JSONB NOT NULL DEFAULT '[]'::jsonb,
            human_override BOOLEAN NOT NULL DEFAULT FALSE,
            override_by UUID REFERENCES users(id) ON DELETE SET NULL,
            override_reason TEXT,
            override_at TIMESTAMP WITH TIME ZONE,
            prev_hash VARCHAR(64),
            input_hash VARCHAR(64),
            extra_data JSONB NOT NULL DEFAULT '{}'::jsonb
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_decision_logs_timestamp ON ai_decision_logs(timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_decision_logs_agent_name ON ai_decision_logs(agent_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_decision_logs_decision_type ON ai_decision_logs(decision_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_decision_logs_assessment_id ON ai_decision_logs(assessment_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_decision_logs_agent_timestamp ON ai_decision_logs(agent_name, timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_decision_logs_decision_timestamp ON ai_decision_logs(decision_type, timestamp)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            user_email VARCHAR(255),
            action VARCHAR(100) NOT NULL,
            entity_type VARCHAR(100),
            entity_id VARCHAR(100),
            old_values JSONB NOT NULL DEFAULT '{}'::jsonb,
            new_values JSONB NOT NULL DEFAULT '{}'::jsonb,
            ip_address VARCHAR(64),
            user_agent TEXT,
            session_id VARCHAR(100),
            prev_hash VARCHAR(64),
            input_hash VARCHAR(64)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_timestamp ON audit_logs(timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs(entity_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_id ON audit_logs(entity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_action_timestamp ON audit_logs(action, timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_timestamp ON audit_logs(user_id, timestamp)")

    print("OK: ai_decision_logs and audit_logs tables (re)created with 14 indexes")


def downgrade():
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS ai_decision_logs CASCADE")
    print("OK: ai_decision_logs and audit_logs tables dropped")
