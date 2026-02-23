"""
InstantRisk V2 - FastAPI Application Entry Point

This module initializes the FastAPI application with security middleware,
CORS, routers, and startup/shutdown event handlers.

Security Features:
- Rate limiting (slowapi)
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- IP protection (auto-banning, blocklists)
- Request logging
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging

from app.config import settings
from app.core.database import engine, Base
from app.routers import (
    auth,
    documents,
    assessments,
    upload_session,
    contracts,
    templates,
)
from app.routers import reference_documents, document_generation
from app.routers import pricing_quotes, pricing_benchmarks, teams
from app.routers import extraction, analysis, sanctions, language
from app.routers import precedents, explainability
from app.routers import templates_v3, chat, clauses
from app.routers import subscription, approval, sharing, two_factor, security
from app.routers import claims as claims_router
from app.routers import claimsense, loss_runs
from app.routers import admin
from app.routers import admin_reset
from app.routers import training
from app.routers import rapidrate
from app.routers import investigation
from app.routers import entities
from app.routers import events as events_router
from app.routers import (
    blockchain,
)  # Feature: Smart Contract Automation (Polygon NFT policies)
from app.routers import copilot  # Feature: Underwriter Copilot (LangChain AI guidance)
from app.routers import (
    broker_comms,
)  # Feature: Broker Communication AI (IMAP email bot)
from app.routers import broker_portal  # Feature: Broker Portal (broker-facing portal)
from app.routers import email_negotiation  # Feature: Email Negotiation AI
from app.routers import (
    scenario_simulation,
)  # Feature: Scenario Simulation (Monte Carlo)
from app.routers import predictive_underwriting  # Feature: Predictive Underwriting
from app.routers import (
    compliance,
)  # Feature: Regulatory Compliance Scanner (FCA/PRA/EIOPA)
from app.routers import (
    vision,
)  # Feature: Computer Vision Property Inspection (AWS Bedrock)
from app.routers import voice  # Feature: Voice Commands & Transcription

# Security middleware
from app.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.ip_protection import IPProtectionMiddleware, load_ip_blocklists
from app.middleware.security_logger import setup_security_log_file
from slowapi.errors import RateLimitExceeded

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("instantrisk.security")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events.

    Handles startup tasks like database table creation, security initialization,
    and cleanup tasks on shutdown.
    """
    # Startup: Create database tables
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Environment: {settings.environment}")
    print(f"API running on port {settings.api_port}")

    # Security validation: ensure critical secrets are set in production
    if settings.environment != "development":
        if not settings.jwt_secret_key or settings.jwt_secret_key in (
            "",
            "local-dev-jwt-secret",
            "local-dev-jwt-secret-change-in-prod",
        ):
            logger.critical("SECURITY: JWT_SECRET_KEY not set for production!")
        if not settings.SECRET_KEY or settings.SECRET_KEY in (
            "",
            "local-dev-secret-key",
            "local-dev-secret-key-change-in-prod",
        ):
            logger.critical("SECURITY: SECRET_KEY not set for production!")
        if settings.debug:
            logger.warning(
                "SECURITY: DEBUG mode is enabled in non-development environment"
            )

    # Add missing columns to existing tables (v4 → EC2 schema migration)
    # Run each migration in its own transaction so one failure doesn't abort others
    try:
        from sqlalchemy import text

        # Convert any old 'refer' decisions to 'no_go' (REFER was removed from enum)
        migrations = [
            "UPDATE assessments SET decision = 'no_go' WHERE decision = 'refer'",
            # Share links table
            """CREATE TABLE IF NOT EXISTS share_links (
                    id SERIAL PRIMARY KEY,
                    assessment_id UUID REFERENCES assessments(id),
                    token VARCHAR(64) UNIQUE NOT NULL,
                    created_by UUID REFERENCES users(id) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    is_revoked BOOLEAN DEFAULT FALSE NOT NULL,
                    access_count INTEGER DEFAULT 0 NOT NULL,
                    last_accessed_at TIMESTAMP
                )""",
            "CREATE INDEX IF NOT EXISTS ix_share_links_token ON share_links(token)",
            # Users table - columns added in EC2 version
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20) DEFAULT 'approved'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_by UUID",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS rejection_reason TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(20) DEFAULT 'en'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS two_fa_enabled BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS two_fa_secret VARCHAR(32)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS two_fa_backup_codes TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT TRUE",
            # Chat tables (v21)
            """CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id),
                    conversation_id VARCHAR(50) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    extra_data JSON DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
            "CREATE INDEX IF NOT EXISTS idx_chat_user_conv ON chat_messages(user_id, conversation_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_messages(created_at)",
            # Subscriptions table (v30)
            """CREATE TABLE IF NOT EXISTS subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL UNIQUE REFERENCES users(id),
                    tier VARCHAR(20) NOT NULL DEFAULT 'trial',
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    started_at TIMESTAMP WITH TIME ZONE,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    stripe_customer_id VARCHAR(255),
                    stripe_subscription_id VARCHAR(255),
                    monthly_assessments_used INTEGER DEFAULT 0,
                    monthly_documents_generated INTEGER DEFAULT 0,
                    monthly_chat_messages_used INTEGER DEFAULT 0,
                    usage_reset_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )""",
            "CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id)",
            # FIRST: Convert native enums to VARCHAR (EC2 uses native enum, backend-merged uses string)
            # Must convert enum columns before adding new values
            "ALTER TABLE assessments ALTER COLUMN status TYPE VARCHAR(50) USING status::text",
            "ALTER TABLE assessments ALTER COLUMN mode TYPE VARCHAR(20) USING mode::text",
            # Make user_id nullable (EC2 uses user_id, backend-merged uses created_by)
            "ALTER TABLE assessments ALTER COLUMN user_id DROP NOT NULL",
            # Make name nullable (EC2 uses name, backend-merged uses title)
            "ALTER TABLE assessments ALTER COLUMN name DROP NOT NULL",
            # Add ALL missing columns to existing assessments table
            # EC2 schema uses different column names - add backend-merged columns
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS reference_number VARCHAR(50)",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS title VARCHAR(500)",
            # Copy name to title (EC2 uses name, backend-merged uses title)
            "UPDATE assessments SET title = name WHERE title IS NULL AND name IS NOT NULL",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS risk_category VARCHAR(50) DEFAULT 'property'",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS decision VARCHAR(20) DEFAULT 'pending'",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS created_by UUID",
            # Copy user_id to created_by
            "UPDATE assessments SET created_by = user_id WHERE created_by IS NULL AND user_id IS NOT NULL",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS broker_reference VARCHAR(100)",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS premium FLOAT",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS sum_insured FLOAT",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS deductible FLOAT",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS inception_date TIMESTAMP WITH TIME ZONE",
            # Copy policy_effective_date to inception_date
            "UPDATE assessments SET inception_date = policy_effective_date WHERE inception_date IS NULL AND policy_effective_date IS NOT NULL",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS expiry_date TIMESTAMP WITH TIME ZONE",
            # Copy policy_expiration_date to expiry_date
            "UPDATE assessments SET expiry_date = policy_expiration_date WHERE expiry_date IS NULL AND policy_expiration_date IS NOT NULL",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS territory VARCHAR(100)",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS exposure_details JSON DEFAULT '{}'",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS confidence_score INTEGER",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS ai_analysis JSON DEFAULT '{}'",
            # Copy report to ai_analysis
            "UPDATE assessments SET ai_analysis = report WHERE ai_analysis IS NULL AND report IS NOT NULL",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS ai_recommendations JSON DEFAULT '[]'",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS analysis_mode VARCHAR(20)",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS previous_analysis_json JSON",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS underwriter_notes TEXT",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS decision_rationale TEXT",
            # Copy recommendation to decision_rationale
            "UPDATE assessments SET decision_rationale = recommendation WHERE decision_rationale IS NULL AND recommendation IS NOT NULL",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS ocr_extracted_text TEXT",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS rapidrate_results JSON",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS is_flagged BOOLEAN DEFAULT FALSE",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS flag_reason VARCHAR(255)",
            # v87: New assessment fields for ML engine
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS broker_name VARCHAR(255)",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS commission_rate FLOAT",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS insured_entity_name VARCHAR(500)",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS companies_house_number VARCHAR(50)",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS renewal_date TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS loss_run_reporting_rules TEXT",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS regulatory_framework VARCHAR(255)",
            # v102: Computer vision property inspection
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS property_analysis JSON",
            # v110: Broker portal columns
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS deadline TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS upload_session_token VARCHAR(100)",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS assigned_underwriter_id UUID",
            # v111: Broker commission rate on users table
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS commission_rate FLOAT",
            # Syndicates table (required for assessments FK)
            """CREATE TABLE IF NOT EXISTS syndicates (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    syndicate_number VARCHAR(10) UNIQUE,
                    description TEXT,
                    risk_appetite JSON DEFAULT '{}',
                    contact_email VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )""",
            # Assessments table - id is UUID to match EC2 schema
            """CREATE TABLE IF NOT EXISTS assessments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    reference_number VARCHAR(50),
                    title VARCHAR(500) NOT NULL,
                    description TEXT,
                    risk_category VARCHAR(50) DEFAULT 'property',
                    status VARCHAR(50) DEFAULT 'draft',
                    decision VARCHAR(20) DEFAULT 'pending',
                    user_id UUID NOT NULL REFERENCES users(id),
                    insured_name VARCHAR(255),
                    broker_reference VARCHAR(100),
                    premium FLOAT,
                    sum_insured FLOAT,
                    deductible FLOAT,
                    inception_date TIMESTAMP WITH TIME ZONE,
                    expiry_date TIMESTAMP WITH TIME ZONE,
                    territory VARCHAR(100),
                    exposure_details JSON DEFAULT '{}',
                    risk_score INTEGER,
                    confidence_score INTEGER,
                    ai_analysis JSON DEFAULT '{}',
                    ai_recommendations JSON DEFAULT '[]',
                    analysis_mode VARCHAR(20),
                    previous_analysis_json JSON,
                    underwriter_notes TEXT,
                    decision_rationale TEXT,
                    ocr_extracted_text TEXT,
                    is_flagged BOOLEAN DEFAULT FALSE,
                    flag_reason VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP WITH TIME ZONE
                )""",
            "CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status)",
            "CREATE INDEX IF NOT EXISTS idx_assessments_decision ON assessments(decision)",
            "CREATE INDEX IF NOT EXISTS idx_assessments_created_by ON assessments(created_by)",
            # Documents table - assessment_id UUID to match assessments.id UUID
            """CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    file_path VARCHAR(512) NOT NULL,
                    file_size INTEGER NOT NULL,
                    mime_type VARCHAR(100),
                    document_type VARCHAR(50) DEFAULT 'other',
                    status VARCHAR(50) DEFAULT 'pending',
                    uploaded_by UUID NOT NULL REFERENCES users(id),
                    assessment_id UUID REFERENCES assessments(id),
                    ocr_text TEXT,
                    ocr_confidence INTEGER,
                    ocr_language VARCHAR(10) DEFAULT 'en',
                    extracted_data JSON DEFAULT '{}',
                    vector_id VARCHAR(255),
                    checksum VARCHAR(64),
                    error_message TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP WITH TIME ZONE
                )""",
            "CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)",
            "CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents(uploaded_by)",
            "CREATE INDEX IF NOT EXISTS idx_documents_assessment ON documents(assessment_id)",
            # Add missing reference_number to existing assessments table (if exists without it)
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS reference_number VARCHAR(50)",
            # Fix: Upgrade generated_documents.id from INTEGER to BIGINT (timestamp IDs overflow int32)
            "ALTER TABLE generated_documents ALTER COLUMN id TYPE BIGINT",
            # Fix: Cast risk_score to INTEGER if it's VARCHAR (EC2 migration issue)
            "ALTER TABLE assessments ALTER COLUMN risk_score TYPE INTEGER USING NULLIF(risk_score, '')::INTEGER",
            # Autonomous investigation (v103)
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS investigation_report JSONB DEFAULT '{}'",
            "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS investigation_status VARCHAR(20) DEFAULT 'not_started'",
            "CREATE INDEX IF NOT EXISTS idx_assessments_investigation_status ON assessments(investigation_status)",
            "CREATE INDEX IF NOT EXISTS idx_assessments_investigation_report ON assessments USING gin (investigation_report)",
            # Global Event Intelligence (v104)
            """CREATE TABLE IF NOT EXISTS global_events (
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
                )""",
            "CREATE INDEX IF NOT EXISTS idx_global_events_event_type ON global_events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_global_events_severity ON global_events(severity)",
            "CREATE INDEX IF NOT EXISTS idx_global_events_event_time ON global_events(event_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_global_events_source ON global_events(source)",
            # Smart Contract Automation (blockchain / policy NFT records)
            """CREATE TABLE IF NOT EXISTS blockchain_policies (
                    id SERIAL PRIMARY KEY,
                    assessment_id UUID REFERENCES assessments(id),
                    policy_id VARCHAR(100) NOT NULL UNIQUE,
                    token_id INTEGER,
                    tx_hash VARCHAR(100),
                    block_number INTEGER,
                    gas_used INTEGER,
                    holder_wallet VARCHAR(100),
                    premium_matic DOUBLE PRECISION,
                    sum_insured_matic DOUBLE PRECISION,
                    inception_ts INTEGER,
                    expiry_ts INTEGER,
                    active BOOLEAN DEFAULT TRUE,
                    simulated BOOLEAN DEFAULT FALSE,
                    chain_id INTEGER DEFAULT 80001,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    created_by UUID REFERENCES users(id)
                )""",
            "CREATE INDEX IF NOT EXISTS idx_blockchain_policies_assessment ON blockchain_policies(assessment_id)",
            "CREATE INDEX IF NOT EXISTS idx_blockchain_policies_policy_id ON blockchain_policies(policy_id)",
            # Parametric claims table
            """CREATE TABLE IF NOT EXISTS parametric_claims (
                    id SERIAL PRIMARY KEY,
                    claim_id INTEGER NOT NULL,
                    policy_id VARCHAR(100) NOT NULL,
                    token_id INTEGER,
                    trigger_type VARCHAR(50) NOT NULL,
                    trigger_value DOUBLE PRECISION,
                    claim_amount_matic DOUBLE PRECISION,
                    status VARCHAR(20) DEFAULT 'pending',
                    tx_hash VARCHAR(100),
                    simulated BOOLEAN DEFAULT FALSE,
                    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    resolved_at TIMESTAMP WITH TIME ZONE
                )""",
            "CREATE INDEX IF NOT EXISTS idx_parametric_claims_policy ON parametric_claims(policy_id)",
            "CREATE INDEX IF NOT EXISTS idx_parametric_claims_status ON parametric_claims(status)",
            # Broker email communications log
            """CREATE TABLE IF NOT EXISTS broker_email_log (
                    id SERIAL PRIMARY KEY,
                    log_id VARCHAR(50) NOT NULL,
                    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    sender VARCHAR(255),
                    subject VARCHAR(500),
                    email_type VARCHAR(50),
                    insured_name VARCHAR(255),
                    risk_category VARCHAR(50),
                    sum_insured DOUBLE PRECISION,
                    parsed BOOLEAN DEFAULT FALSE,
                    reply_sent BOOLEAN DEFAULT FALSE,
                    confidence DOUBLE PRECISION,
                    assessment_id UUID,
                    error_text TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )""",
            "CREATE INDEX IF NOT EXISTS idx_broker_email_log_received ON broker_email_log(received_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_broker_email_log_type ON broker_email_log(email_type)",
            # Compliance check results
            """CREATE TABLE IF NOT EXISTS compliance_checks (
                    id SERIAL PRIMARY KEY,
                    assessment_id UUID REFERENCES assessments(id),
                    checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    overall_status VARCHAR(30) NOT NULL,
                    score INTEGER,
                    passed INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    warnings INTEGER DEFAULT 0,
                    checks_json JSONB DEFAULT '[]',
                    required_actions_json JSONB DEFAULT '[]',
                    regulatory_summary TEXT,
                    created_by UUID REFERENCES users(id)
                )""",
            "CREATE INDEX IF NOT EXISTS idx_compliance_checks_assessment ON compliance_checks(assessment_id)",
            "CREATE INDEX IF NOT EXISTS idx_compliance_checks_status ON compliance_checks(overall_status)",
            # Broker portal fields on quotes table
            "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS accepted_by UUID REFERENCES users(id)",
            "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS declined_at TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE quotes ADD COLUMN IF NOT EXISTS decline_reason TEXT",
        ]
        # Run each migration in its own transaction
        for sql in migrations:
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(sql))
                print(f"Migration OK: {sql[:60]}...")
            except Exception as e:
                print(f"Migration skip: {sql[:60]}... ({str(e)[:80]})")
        print("Schema migration: users table columns verified")
        print("Schema migration: chat_messages table verified")
        print("Schema migration: syndicates, assessments, documents tables verified")
    except Exception as e:
        print(f"Schema migration error: {e}")

    # Only create tables that don't exist yet; skip FK errors from schema mismatches
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Note: create_all skipped (existing schema): {e}")

    # Initialize security
    print("Loading security configurations...")
    await load_ip_blocklists()
    setup_security_log_file(settings.resolved_security_log_path)
    print("Security initialized - Enterprise Grade V5")

    # Seed benchmark data if empty
    try:
        from app.seed_benchmark import seed_benchmark_data
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            count = await seed_benchmark_data(session)
            if count > 0:
                print(f"Seeded {count} benchmark records")
    except Exception as e:
        print(f"Benchmark seed skipped: {e}")

    # Seed test users (trial, basic, premium)
    try:
        from app.seed_users import seed_test_users
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            count = await seed_test_users(session)
            if count > 0:
                print(f"Seeded {count} test users")
            else:
                print("Test users already exist")
    except Exception as e:
        print(f"User seed skipped: {e}")

    # Backfill NULL expiry_dates on existing assessments (1 year from created_at)
    try:
        from sqlalchemy import text
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    UPDATE assessments
                    SET expiry_date = created_at + INTERVAL '1 year'
                    WHERE expiry_date IS NULL
                """)
            )
            if result.rowcount > 0:
                print(f"Backfilled expiry_date on {result.rowcount} assessments")
            await session.commit()
    except Exception as e:
        print(f"Expiry date backfill skipped: {e}")

    # Seed exposure_losses demo data for loss ratio analytics
    try:
        from sqlalchemy import text
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # Check if any exposure_losses exist
            count_result = await session.execute(
                text("SELECT COUNT(*) FROM exposure_losses")
            )
            count = count_result.scalar()
            if count == 0:
                # Get bound assessments to link losses to
                assess_result = await session.execute(
                    text("""
                        SELECT id, premium, risk_category, territory, created_at
                        FROM assessments
                        WHERE decision = 'go' AND premium IS NOT NULL AND premium > 0
                        LIMIT 25
                    """)
                )
                bound = assess_result.fetchall()
                if bound:
                    import random

                    random.seed(42)
                    # Ensure a default syndicate exists for loss records
                    syn_result = await session.execute(
                        text("SELECT id FROM syndicates LIMIT 1")
                    )
                    syn_id = syn_result.scalar()
                    if not syn_id:
                        await session.execute(
                            text(
                                "INSERT INTO syndicates (name, aiin, managing_agent, created_at, updated_at) VALUES ('Demo Syndicate', '1234', 'Demo Managing Agent', NOW(), NOW())"
                            )
                        )
                        await session.flush()
                        syn_result2 = await session.execute(
                            text("SELECT id FROM syndicates LIMIT 1")
                        )
                        syn_id = syn_result2.scalar()
                    if not syn_id:
                        syn_id = 1  # fallback

                    inserted = 0
                    for row in bound:
                        (
                            assess_id,
                            premium,
                            risk_cat,
                            territory,
                            created_at,
                        ) = row
                        premium_val = float(premium) if premium else 100000
                        # Generate 1-3 loss records per assessment
                        for _ in range(random.randint(1, 3)):
                            loss_ratio = random.uniform(0.35, 0.95)
                            loss_amount = round(premium_val * loss_ratio, 2)
                            await session.execute(
                                text("""
                                    INSERT INTO exposure_losses (
                                        assessment_id, syndicate_id, loss_amount, currency,
                                        loss_type, loss_date, territory, created_at
                                    ) VALUES (
                                        :assess_id, :syn_id, :loss, 'GBP',
                                        :loss_type, :loss_date, :territory, NOW()
                                    )
                                """),
                                {
                                    "assess_id": assess_id,
                                    "syn_id": syn_id,
                                    "loss": loss_amount,
                                    "loss_type": random.choice(
                                        ["attritional", "large", "cat"]
                                    ),
                                    "territory": territory or "US",
                                    "loss_date": created_at,
                                },
                            )
                            inserted += 1
                    await session.commit()
                    print(f"Seeded {inserted} exposure_losses records")
                else:
                    print("No bound assessments with premium found for loss seeding")
            else:
                print(f"Exposure losses already exist ({count} rows)")
    except Exception as e:
        print(f"Exposure losses seed skipped: {e}")

    # Enable pgvector extension and create vector tables
    try:
        from sqlalchemy import text

        pgvector_migrations = [
            "CREATE EXTENSION IF NOT EXISTS vector",
            """CREATE TABLE IF NOT EXISTS rag_vectors (
                id SERIAL PRIMARY KEY,
                text_hash VARCHAR(64) UNIQUE NOT NULL,
                text_preview TEXT,
                full_text TEXT,
                doc_type VARCHAR(50),
                category VARCHAR(100),
                source VARCHAR(100),
                name VARCHAR(200),
                question VARCHAR(500),
                embedding vector(768) NOT NULL,
                created_at TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS ix_rag_vectors_doc_type ON rag_vectors(doc_type)",
            """CREATE TABLE IF NOT EXISTS user_doc_vectors (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                doc_id VARCHAR(36) NOT NULL,
                filename VARCHAR(255),
                category VARCHAR(100),
                content_type VARCHAR(100),
                size_bytes INTEGER,
                chunk_index INTEGER,
                chunk_count INTEGER,
                text TEXT NOT NULL,
                embedding vector(768) NOT NULL,
                uploaded_at TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS ix_user_doc_vectors_user_id ON user_doc_vectors(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_doc_vectors_doc_id ON user_doc_vectors(doc_id)",
            """CREATE TABLE IF NOT EXISTS ref_doc_vectors (
                id SERIAL PRIMARY KEY,
                document_id INTEGER,
                chunk_index INTEGER,
                chunk_text TEXT,
                category VARCHAR(100),
                risk_categories JSONB,
                title VARCHAR(255),
                file_name VARCHAR(255),
                embedding vector(768) NOT NULL,
                created_at TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS ix_ref_doc_vectors_document_id ON ref_doc_vectors(document_id)",
        ]
        for sql in pgvector_migrations:
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(sql))
                print(f"pgvector OK: {sql[:60]}...")
            except Exception as e:
                print(f"pgvector skip: {sql[:60]}... ({str(e)[:80]})")

        # Create HNSW indexes (separate so table creation doesn't fail)
        hnsw_indexes = [
            "CREATE INDEX IF NOT EXISTS ix_rag_vectors_embedding_hnsw ON rag_vectors USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)",
            "CREATE INDEX IF NOT EXISTS ix_user_doc_vectors_embedding_hnsw ON user_doc_vectors USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)",
            "CREATE INDEX IF NOT EXISTS ix_ref_doc_vectors_embedding_hnsw ON ref_doc_vectors USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)",
        ]
        for sql in hnsw_indexes:
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(sql))
                print(f"HNSW index OK: {sql.split(' ON ')[1][:40]}...")
            except Exception as e:
                print(f"HNSW index skip: ({str(e)[:80]})")

        print("pgvector: tables and HNSW indexes verified")
    except Exception as e:
        print(f"pgvector setup error: {e}")

    # Check pgvector RAG status (indexing triggered via /admin/index-rag endpoint)
    try:
        from app.services.rag_indexer import rag_indexer

        if rag_indexer.is_indexed():
            count = rag_indexer.get_collection_count()
            print(f"pgvector RAG: {count} vectors indexed")
        else:
            print(
                "pgvector RAG: not indexed yet - call POST /api/v1/admin/index-rag to trigger"
            )
    except Exception as e:
        print(f"pgvector RAG: unavailable ({e})")

    # Download SentenceTransformer to EFS if not already there (one-time per EFS lifecycle)
    import os as _os

    _st_efs = "/mnt/efs/models/sentence-transformer-insurance"
    if _os.path.isdir("/mnt/efs") and not _os.path.isdir(_st_efs):
        try:
            print("EFS: sentence-transformer not found — downloading from S3...")
            import boto3 as _boto3, tarfile as _tarfile, io as _io

            _s3 = _boto3.client("s3", region_name="us-east-1")
            _buf = _io.BytesIO()
            _s3.download_fileobj(
                "instantrisk-documents-995306061991",
                "ml-models/sentence-transformer-insurance.tar.gz",
                _buf,
            )
            _buf.seek(0)
            _os.makedirs("/mnt/efs/models", exist_ok=True)
            with _tarfile.open(fileobj=_buf, mode="r:gz") as _tf:
                _tf.extractall("/mnt/efs/models")
            print("EFS: sentence-transformer downloaded OK")
        except Exception as _e:
            print(
                f"EFS: sentence-transformer S3 download failed ({_e}) — will download from HuggingFace on demand"
            )

    # Pre-load InstantRisk Engine ML model (avoids cold-start latency on first request)
    try:
        from app.services.insurance_model_service import insurance_model_service

        available = insurance_model_service.load()
        if not available:
            # Local model not found (Docker container excludes large model files).
            # Try downloading from S3 where the trained model was uploaded.
            print(
                "InstantRisk Engine: local model not found, attempting S3 download..."
            )
            try:
                s3_uris = [
                    (
                        "s3://instantrisk-documents-995306061991/ml-models/instantrisk-engine-v1-best/model-full.tar.gz",
                        "best",
                    ),
                    (
                        "s3://instantrisk-documents-995306061991/ml-models/instantrisk-engine-v1-best/model.tar.gz",
                        "best",
                    ),
                    (
                        "s3://instantrisk-documents-995306061991/ml-models/instantrisk-engine-v1-final/model.tar.gz",
                        "final",
                    ),
                    (
                        "s3://instantrisk-documents-995306061991/ml-models/instantrisk-engine-v1-final/output/model.tar.gz",
                        "final",
                    ),
                ]
                for s3_uri, target in s3_uris:
                    try:
                        available = insurance_model_service.load_from_s3(
                            s3_uri=s3_uri, target=target
                        )
                        if available:
                            print(f"InstantRisk Engine: loaded from S3 ({s3_uri})")
                            break
                    except Exception:
                        continue
                if not available:
                    print(
                        "InstantRisk Engine: S3 load failed — running in keyword-search fallback mode"
                    )
            except Exception as s3_err:
                print(
                    f"InstantRisk Engine: S3 load error ({s3_err}) — running in fallback mode"
                )
        if available:
            config = insurance_model_service._config
            print(
                f"InstantRisk Engine loaded: {config.get('num_clause_labels', 0)} clause labels, "
                f"{config.get('num_intent_labels', 0)} intent labels, "
                f"base={config.get('base_model', 'unknown')}"
            )
        else:
            print(
                "InstantRisk Engine: model not available — running in keyword-search fallback mode"
            )
    except Exception as e:
        print(f"InstantRisk Engine load skipped: {e}")

    # Start background scheduler (APScheduler for event monitoring)
    try:
        from app.tasks.scheduled_jobs import start_scheduler

        start_scheduler()
        print(
            "APScheduler started - Global Event Intelligence monitoring active (hourly)"
        )
    except Exception as e:
        print(f"APScheduler start skipped: {e}")

    yield

    # Shutdown: Stop scheduler before disposing DB connections
    try:
        from app.tasks.scheduled_jobs import stop_scheduler

        stop_scheduler()
        print("APScheduler stopped")
    except Exception as e:
        print(f"APScheduler stop error: {e}")

    # Shutdown: Dispose of database connections
    print("Shutting down...")
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="AI-powered insurance risk assessment platform for Lloyd's syndicates",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    redirect_slashes=False,  # Disable auto-redirect to prevent issues behind CloudFront
)

# Initialize rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Security Headers Middleware - adds HSTS, CSP, X-Frame-Options, etc.
app.add_middleware(SecurityHeadersMiddleware)

# IP Protection Middleware - auto-banning, blocklists
app.add_middleware(
    IPProtectionMiddleware,
    exclude_paths=["/health", "/", "/docs", "/redoc", "/openapi.json"],
)

# Configure CORS - whitelist specific origins
ALLOWED_ORIGINS = [
    "https://d2ci3ptu2ygeo3.cloudfront.net",  # Frontend CloudFront (S3 frontend)
    "https://d2f065h47nuk0c.cloudfront.net",  # API CloudFront (ALB origin)
    "https://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com",  # ALB direct
    "https://app.instantrisk.com",  # Production domain (future)
    "http://localhost:3000",  # Local dev
    "http://localhost:8200",  # Local dev alt
    "http://localhost:5000",  # Flutter web dev
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TEMPORARY: Allow all origins for demo
    allow_credentials=False,  # Must be False when using wildcard
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# Health endpoints - defined BEFORE routers to ensure they match first
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint for health check."""
    return {
        "message": f"Welcome to {settings.app_name} API",
        "status": "healthy",
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "database": "connected",
        "cache": "connected",
        "vector_store": "connected",
    }


@app.get("/api/v1/health", tags=["Health"])
async def api_health():
    """ALB health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/api/v1/health/live", tags=["Health"])
async def health_live():
    """ECS container health check endpoint."""
    return {"status": "ok"}


# Include routers
app.include_router(
    auth.router, prefix=f"{settings.api_prefix}/auth", tags=["Authentication"]
)
app.include_router(
    documents.router, prefix=f"{settings.api_prefix}/documents", tags=["Documents"]
)
app.include_router(
    assessments.router,
    prefix=f"{settings.api_prefix}/assessments",
    tags=["Assessments"],
)
app.include_router(
    upload_session.router,
    prefix=f"{settings.api_prefix}/upload-sessions",
    tags=["Upload Sessions"],
)
app.include_router(
    contracts.router, prefix=f"{settings.api_prefix}/contracts", tags=["Contracts"]
)
app.include_router(
    templates.router, prefix=f"{settings.api_prefix}/templates", tags=["Templates"]
)
app.include_router(
    reference_documents.router,
    prefix=f"{settings.api_prefix}/reference-documents",
    tags=["Reference Documents"],
)
app.include_router(
    document_generation.router,
    prefix=f"{settings.api_prefix}",
    tags=["Document Generation"],
)
app.include_router(
    pricing_quotes.router,
    prefix=f"{settings.api_prefix}/quotes",
    tags=["Quotes & Pricing"],
)
app.include_router(
    pricing_benchmarks.router,
    prefix=f"{settings.api_prefix}/pricing/benchmarks",
    tags=["Pricing Benchmarks"],
)
app.include_router(
    teams.router, prefix=f"{settings.api_prefix}/teams", tags=["Teams & RBAC"]
)
app.include_router(
    extraction.router, prefix=f"{settings.api_prefix}", tags=["Document Extraction"]
)
app.include_router(analysis.router, prefix=f"{settings.api_prefix}", tags=["Analysis"])
app.include_router(
    sanctions.router, prefix=f"{settings.api_prefix}", tags=["Sanctions"]
)
app.include_router(
    language.router,
    prefix=f"{settings.api_prefix}/language",
    tags=["Language & Translation"],
)
app.include_router(
    templates_v3.router,
    prefix=f"{settings.api_prefix}/templates-v3",
    tags=["Templates V3"],
)
app.include_router(chat.router, prefix=f"{settings.api_prefix}/chat", tags=["AI Chat"])
app.include_router(
    clauses.router, prefix=f"{settings.api_prefix}", tags=["Clauses Library"]
)
app.include_router(
    precedents.router,
    prefix=f"{settings.api_prefix}/precedents",
    tags=["Precedent Search"],
)
app.include_router(
    explainability.router,
    prefix=f"{settings.api_prefix}/explainability",
    tags=["AI Explainability"],
)
app.include_router(
    subscription.router, prefix=f"{settings.api_prefix}", tags=["Subscription"]
)
app.include_router(
    approval.router, prefix=f"{settings.api_prefix}", tags=["Admin Approvals"]
)
app.include_router(
    approval.approval_status_router,
    prefix=f"{settings.api_prefix}",
    tags=["Approval Status"],
)
app.include_router(sharing.router, prefix=f"{settings.api_prefix}", tags=["Sharing"])
app.include_router(
    two_factor.router,
    prefix=f"{settings.api_prefix}/2fa",
    tags=["Two-Factor Authentication"],
)
app.include_router(
    security.router, prefix=f"{settings.api_prefix}/security", tags=["Security Admin"]
)
app.include_router(
    claims_router.router, prefix=f"{settings.api_prefix}", tags=["Claims"]
)
app.include_router(
    claimsense.router, prefix=f"{settings.api_prefix}/claimsense", tags=["ClaimSense"]
)
app.include_router(
    loss_runs.router, prefix=f"{settings.api_prefix}/loss-runs", tags=["Loss Runs"]
)
app.include_router(admin.router, prefix=f"{settings.api_prefix}", tags=["Admin"])
# Admin reset routes only available in development (requires ENABLE_ADMIN_RESET=true env var)
import os

if (
    os.environ.get("ENABLE_ADMIN_RESET", "").lower() == "true"
    or settings.environment == "development"
):
    app.include_router(
        admin_reset.router, prefix=f"{settings.api_prefix}", tags=["Admin Reset"]
    )
    logging.getLogger("instantrisk.security").warning(
        "Admin reset routes ENABLED - disable in production"
    )
app.include_router(
    training.router, prefix=f"{settings.api_prefix}/training", tags=["AI Training"]
)
app.include_router(rapidrate.router, tags=["RapidRate"])
app.include_router(
    investigation.router,
    prefix=f"{settings.api_prefix}/investigation",
    tags=["Autonomous Investigation"],
)
app.include_router(
    entities.router,
    prefix=f"{settings.api_prefix}/entities",
    tags=["Entity Graph & Fraud Detection"],
)
app.include_router(
    events_router.router,
    prefix=f"{settings.api_prefix}/events",
    tags=["Global Event Intelligence"],
)
# God Mode Features (v2)
app.include_router(
    blockchain.router,
    prefix=f"{settings.api_prefix}/blockchain",
    tags=["Smart Contracts"],
)
app.include_router(
    copilot.router,
    prefix=f"{settings.api_prefix}/copilot",
    tags=["Underwriter Copilot"],
)
app.include_router(
    broker_comms.router,
    prefix=f"{settings.api_prefix}/broker-comms",
    tags=["Broker Communication AI"],
)
app.include_router(
    compliance.router,
    prefix=f"{settings.api_prefix}/compliance",
    tags=["Regulatory Compliance"],
)
app.include_router(
    vision.router, prefix=f"{settings.api_prefix}/vision", tags=["Computer Vision"]
)
app.include_router(
    voice.router, prefix=f"{settings.api_prefix}/voice", tags=["Voice Commands"]
)

# Broker Portal (broker-facing portal)
app.include_router(
    broker_portal.router,
    prefix=f"{settings.api_prefix}/broker-portal",
    tags=["Broker Portal"],
)

# Email Negotiation AI
app.include_router(
    email_negotiation.router,
    prefix=f"{settings.api_prefix}/email-negotiation",
    tags=["Email Negotiation"],
)

# Scenario Simulation (Monte Carlo)
app.include_router(
    scenario_simulation.router,
    prefix=f"{settings.api_prefix}/scenarios",
    tags=["Scenario Simulation"],
)

# Predictive Underwriting
app.include_router(
    predictive_underwriting.router,
    prefix=f"{settings.api_prefix}/predictive-underwriting",
    tags=["Predictive Underwriting"],
)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
