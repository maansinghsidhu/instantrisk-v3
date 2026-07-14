"""Add email_connections and email_ingestion_events tables

Revision ID: 122_email_integrations
Revises: 121_audit_log_partitions
Create Date: 2026-07-12 00:00:00

Adds tables for user-connected Gmail/Outlook email ingestion via OAuth 2.0
and IMAP app-password auth. Supports OAuth REST and IMAP sync workers with
deduplication by provider message ID (OAuth) or UIDVALIDITY:UID (IMAP).

Token encryption: EMAIL_TOKEN_ENCRYPTION_KEY must be set.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID


revision = '122_email_integrations'
down_revision = '121_audit_log_partitions'
branch_labels = None
depends_on = None


def upgrade():
    # ---- email_connections ---------------------------------------------------
    op.execute("""
        CREATE TABLE email_connections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

            -- Provider identity
            provider VARCHAR(20) NOT NULL,
            auth_method VARCHAR(20) NOT NULL DEFAULT 'oauth',
            email_address VARCHAR(255) NOT NULL,
            display_name VARCHAR(255),
            avatar_url VARCHAR(512),

            -- Status
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            error_message TEXT,

            -- Encrypted credentials (Fernet; never in logs/schemas)
            encrypted_access_token TEXT,
            encrypted_refresh_token TEXT,
            encrypted_app_password TEXT,
            encrypted_client_secret TEXT,

            -- OAuth expiry
            token_expires_at TIMESTAMPTZ,

            -- IMAP host (restricted to imap.gmail.com / outlook.office365.com)
            imap_host VARCHAR(255),
            imap_port INTEGER DEFAULT 993,

            -- Sync state
            last_sync_at TIMESTAMPTZ,
            last_error_at TIMESTAMPTZ,
            total_messages_synced INTEGER DEFAULT 0,
            consecutive_errors INTEGER DEFAULT 0,

            -- Timestamps
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- Constraints
            CONSTRAINT uq_email_connections_user_email UNIQUE (user_id, email_address)
        )
    """)
    op.execute("CREATE INDEX ix_email_connections_user_id ON email_connections(user_id)")
    op.execute("CREATE INDEX ix_email_connections_user_provider ON email_connections(user_id, provider)")

    # ---- email_ingestion_events ---------------------------------------------
    op.execute("""
        CREATE TABLE email_ingestion_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            connection_id UUID NOT NULL REFERENCES email_connections(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

            -- Deduplication key:
            --   OAuth (Gmail/Outlook Graph): provider's immutable message ID
            --   IMAP: UIDVALIDITY:UID
            dedupe_key VARCHAR(255) NOT NULL,

            -- Message metadata
            subject VARCHAR(1000),
            sender VARCHAR(500),
            received_at TIMESTAMPTZ,

            -- Processing outcome
            assessment_id UUID REFERENCES assessments(id) ON DELETE SET NULL,
            document_ids TEXT,  -- JSON array of document IDs
            parse_confidence INTEGER,
            error_message TEXT,
            processed BOOLEAN NOT NULL DEFAULT FALSE,

            -- Timestamp
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- Constraints
            CONSTRAINT uq_ingestion_dedupe UNIQUE (connection_id, dedupe_key)
        )
    """)
    op.execute("CREATE INDEX ix_email_ingestion_events_connection_id ON email_ingestion_events(connection_id)")
    op.execute("CREATE INDEX ix_email_ingestion_events_connection_dedupe ON email_ingestion_events(connection_id, dedupe_key)")

    print("OK: email_connections and email_ingestion_events tables created")


def downgrade():
    op.execute("DROP TABLE IF EXISTS email_ingestion_events CASCADE")
    op.execute("DROP TABLE IF EXISTS email_connections CASCADE")
    print("OK: email tables dropped")
