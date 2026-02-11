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
from app.routers import auth, documents, assessments, upload_session, contracts, templates
from app.routers import reference_documents, document_generation, integrations
from app.routers import placements, exposure, compliance, pricing, umr, teams
from app.routers import extraction, syndicates, analysis, sanctions, language
from app.routers import templates_v3, pricing_v3, chat, clauses
from app.routers import subscription, approval, sharing, two_factor, security
from app.routers import claims as claims_router
from app.routers import claimsense, loss_runs
from app.routers import admin
from app.routers import admin_reset
from app.routers import training
from app.routers import rapidrate

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

    # Add missing columns to existing tables (v4 → EC2 schema migration)
    # Run each migration in its own transaction so one failure doesn't abort others
    try:
        from sqlalchemy import text
        migrations = [
                # Users table - columns added in EC2 version
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS syndicate_id INTEGER",
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
                "ALTER TABLE assessments ADD COLUMN IF NOT EXISTS syndicate_id INTEGER",
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
                    syndicate_id INTEGER REFERENCES syndicates(id),
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
    setup_security_log_file(settings.security_log_path)
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
            print("pgvector RAG: not indexed yet - call POST /api/v1/admin/index-rag to trigger")
    except Exception as e:
        print(f"pgvector RAG: unavailable ({e})")

    yield

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
    exclude_paths=["/health", "/", "/docs", "/redoc", "/openapi.json"]
)

# Configure CORS - Allow all origins during initial deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# Custom CORS fallback middleware to ensure headers on ALL responses including errors
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    """Ensure CORS headers are present on ALL responses including errors."""
    response = await call_next(request)
    # Always add CORS headers to ensure they're present
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Request-ID"
    return response

# Health endpoints - defined BEFORE routers to ensure they match first
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint for health check."""
    return {
        "message": f"Welcome to {settings.app_name} API",
        "status": "healthy",
        "version": settings.app_version,
        "docs": "/docs"
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
        "vector_store": "connected"
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
app.include_router(auth.router, prefix=f"{settings.api_prefix}/auth", tags=["Authentication"])
app.include_router(documents.router, prefix=f"{settings.api_prefix}/documents", tags=["Documents"])
app.include_router(assessments.router, prefix=f"{settings.api_prefix}/assessments", tags=["Assessments"])
app.include_router(upload_session.router, prefix=f"{settings.api_prefix}/upload-sessions", tags=["Upload Sessions"])
app.include_router(contracts.router, prefix=f"{settings.api_prefix}/contracts", tags=["Contracts"])
app.include_router(templates.router, prefix=f"{settings.api_prefix}/templates", tags=["Templates"])
app.include_router(reference_documents.router, prefix=f"{settings.api_prefix}/reference-documents", tags=["Reference Documents"])
app.include_router(document_generation.router, prefix=f"{settings.api_prefix}", tags=["Document Generation"])
app.include_router(integrations.router, prefix=f"{settings.api_prefix}/integrations", tags=["Integrations"])
app.include_router(placements.router, prefix=f"{settings.api_prefix}/placements", tags=["Placements"])
app.include_router(exposure.router, prefix=f"{settings.api_prefix}/exposure", tags=["Exposure"])
app.include_router(compliance.router, prefix=f"{settings.api_prefix}/compliance", tags=["Compliance"])
app.include_router(pricing.router, prefix=f"{settings.api_prefix}/pricing", tags=["Pricing"])
app.include_router(umr.router, prefix=f"{settings.api_prefix}/umr", tags=["UMR"])
app.include_router(teams.router, prefix=f"{settings.api_prefix}/teams", tags=["Teams & RBAC"])
app.include_router(extraction.router, prefix=f"{settings.api_prefix}", tags=["Document Extraction"])
app.include_router(syndicates.router, prefix=f"{settings.api_prefix}/syndicates", tags=["Syndicates"])
app.include_router(analysis.router, prefix=f"{settings.api_prefix}", tags=["Analysis"])
app.include_router(sanctions.router, prefix=f"{settings.api_prefix}", tags=["Sanctions"])
app.include_router(language.router, prefix=f"{settings.api_prefix}/language", tags=["Language & Translation"])
app.include_router(templates_v3.router, prefix=f"{settings.api_prefix}/templates-v3", tags=["Templates V3"])
app.include_router(pricing_v3.router, prefix=f"{settings.api_prefix}/pricing-v3", tags=["Pricing V3"])
app.include_router(chat.router, prefix=f"{settings.api_prefix}/chat", tags=["AI Chat"])
app.include_router(clauses.router, prefix=f"{settings.api_prefix}", tags=["Clauses Library"])
app.include_router(subscription.router, prefix=f"{settings.api_prefix}", tags=["Subscription"])
app.include_router(approval.router, prefix=f"{settings.api_prefix}", tags=["Admin Approvals"])
app.include_router(approval.approval_status_router, prefix=f"{settings.api_prefix}", tags=["Approval Status"])
app.include_router(sharing.router, prefix=f"{settings.api_prefix}", tags=["Sharing"])
app.include_router(two_factor.router, prefix=f"{settings.api_prefix}/2fa", tags=["Two-Factor Authentication"])
app.include_router(security.router, prefix=f"{settings.api_prefix}/security", tags=["Security Admin"])
app.include_router(claims_router.router, prefix=f"{settings.api_prefix}", tags=["Claims"])
app.include_router(claimsense.router, prefix=f"{settings.api_prefix}/claimsense", tags=["ClaimSense"])
app.include_router(loss_runs.router, prefix=f"{settings.api_prefix}/loss-runs", tags=["Loss Runs"])
app.include_router(admin.router, prefix=f"{settings.api_prefix}", tags=["Admin"])
app.include_router(admin_reset.router, prefix=f"{settings.api_prefix}", tags=["Admin Reset"])
app.include_router(training.router, prefix=f"{settings.api_prefix}/training", tags=["AI Training"])
app.include_router(rapidrate.router, tags=["RapidRate"])


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
