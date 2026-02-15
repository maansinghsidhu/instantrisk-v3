"""
InstantRisk v2 - Admin Router

Administrative endpoints for database management.
Protected by admin authentication.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user, get_current_admin_user, get_password_hash
from app.models.user import User
from app.config import settings

router = APIRouter(prefix="/admin", tags=["Admin"])

# Admin secret from environment variable (fallback for backward compat)
import os
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", settings.SECRET_KEY or "change-me-in-production")

import logging
_admin_logger = logging.getLogger("security.admin")


class ResetResponse(BaseModel):
    success: bool
    message: str
    users_created: int = 0


class UserCreated(BaseModel):
    email: str
    tier: str


@router.post("/reset-demo", response_model=ResetResponse)
async def reset_demo_database(
    secret: str = Query(..., description="Admin secret key"),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset the demo database and create demo users for all 3 tiers.

    This endpoint:
    1. Truncates all assessment-related tables
    2. Creates 3 demo users (trial, basic, premium)

    Requires admin secret key.
    """
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    try:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=365)

        # Step 1: Truncate tables (in order respecting foreign keys)
        tables_to_truncate = [
            "documents",
            "generated_documents",
            "document_generation_jobs",
            "loss_run_summaries",
            "insured_loss_runs",
            "sanctions_screenings",
            "sanctions_matches",
            "share_links",
            "upload_sessions",
            "assessments",
            "templates",
            "reference_documents",
            "custom_templates",
            "chat_messages",
            "chat_message_tools",
            "subscriptions",
            "users",
        ]

        for table in tables_to_truncate:
            try:
                await db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            except Exception as e:
                _admin_logger.debug(f"Truncate {table} skipped: {e}")

        await db.commit()

        # Step 2: Create demo users
        demo_users = [
            {
                "email": "trial@instantrisk.com",
                "full_name": "Trial User",
                "role": "underwriter",
                "tier": "trial"
            },
            {
                "email": "basic@instantrisk.com",
                "full_name": "Basic User",
                "role": "underwriter",
                "tier": "basic"
            },
            {
                "email": "demo@instantrisk.com",
                "full_name": "Premium User",
                "role": "underwriter",
                "tier": "premium"
            }
        ]

        hashed_password = get_password_hash("Demo2026pass")

        for user_data in demo_users:
            user_id = str(uuid.uuid4())

            # Insert user
            await db.execute(text("""
                INSERT INTO users (
                    id, email, full_name, hashed_password, role,
                    is_active, is_verified, approval_status,
                    preferred_language, created_at, updated_at
                ) VALUES (
                    :id, :email, :full_name, :hashed_password, :role,
                    TRUE, TRUE, 'approved',
                    'en', :now, :now
                )
            """), {
                "id": user_id,
                "email": user_data["email"],
                "full_name": user_data["full_name"],
                "hashed_password": hashed_password,
                "role": user_data["role"],
                "now": now
            })

            # Insert subscription
            await db.execute(text("""
                INSERT INTO subscriptions (
                    user_id, tier, status, started_at, expires_at,
                    monthly_assessments_used, monthly_documents_generated,
                    monthly_chat_messages_used, created_at, updated_at
                ) VALUES (
                    :user_id, :tier, 'active', :now, :expires,
                    0, 0, 0, :now, :now
                )
            """), {
                "user_id": user_id,
                "tier": user_data["tier"],
                "now": now,
                "expires": expires
            })

        await db.commit()

        return ResetResponse(
            success=True,
            message="Database reset complete. 3 demo users created.",
            users_created=3
        )

    except Exception as e:
        await db.rollback()
        _admin_logger.error(f"Demo reset failed: {e}")
        raise HTTPException(status_code=500, detail="Reset operation failed")


@router.post("/index-rag")
async def index_rag(
    secret: str = Query(..., description="Admin secret key"),
    force: bool = Query(False, description="Force re-index even if data exists"),
):
    """
    Trigger RAG indexing of JSONL datasets into PostgreSQL pgvector.

    One-time operation — data persists in RDS PostgreSQL.
    """
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    import asyncio
    from app.services.rag_indexer import rag_indexer

    try:
        stats = await asyncio.to_thread(rag_indexer.index_all, force)
        return {"success": True, "stats": stats}
    except Exception as e:
        _admin_logger.error(f"RAG indexing failed: {e}")
        raise HTTPException(status_code=500, detail="Indexing operation failed")


@router.get("/rag-status")
async def rag_status(
    current_user: User = Depends(get_current_admin_user),
):
    """Check RAG indexing status (admin only)."""
    from app.services.rag_indexer import rag_indexer
    try:
        indexed = rag_indexer.is_indexed()
        count = rag_indexer.get_collection_count()
        return {"indexed": indexed, "vector_count": count}
    except Exception as e:
        _admin_logger.error(f"RAG status check failed: {e}")
        return {"indexed": False, "vector_count": 0, "error": "Status check failed"}


@router.get("/health")
async def admin_health(
    current_user: User = Depends(get_current_admin_user),
):
    """Check if admin endpoints are available (admin only)."""
    return {"status": "ok"}
