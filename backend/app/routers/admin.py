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


@router.get("/ml-status")
async def ml_model_status(
    current_user: User = Depends(get_current_admin_user),
):
    """
    Check InstantRisk Engine ML model status.

    Returns model availability, loaded config, and model file sizes.
    Admin only.
    """
    import os
    from app.services.insurance_model_service import insurance_model_service

    # Check local model directories
    base_dir = os.path.join(os.path.dirname(__file__), "..", "data", "models")
    model_dirs = {
        "final": os.path.join(base_dir, "instantrisk-engine-v1-final"),
        "best": os.path.join(base_dir, "instantrisk-engine-v1-best"),
    }

    dir_status = {}
    for slot, path in model_dirs.items():
        if os.path.isdir(path):
            files = {}
            for f in os.listdir(path):
                fpath = os.path.join(path, f)
                files[f] = os.path.getsize(fpath)
            dir_status[slot] = {"exists": True, "files": files}
        else:
            dir_status[slot] = {"exists": False}

    config = {}
    if insurance_model_service._loaded and insurance_model_service._config:
        config = {
            "base_model": insurance_model_service._config.get("base_model"),
            "num_clause_labels": insurance_model_service._config.get("num_clause_labels"),
            "num_intent_labels": insurance_model_service._config.get("num_intent_labels"),
            "training_mode": insurance_model_service._config.get("training_mode"),
        }

    return {
        "model_available": insurance_model_service.is_available,
        "model_loaded": insurance_model_service._loaded,
        "config": config,
        "local_models": dir_status,
    }


@router.post("/ml-load-sagemaker")
async def ml_load_from_sagemaker(
    job_name: str = "instantrisk-engine-20260217-195607",
    target: str = "best",
    current_user: User = Depends(get_current_admin_user),
):
    """
    Download and hot-reload the ML model from a completed SageMaker training job.

    Requires valid AWS credentials in the container environment.
    Admin only.

    Args:
        job_name:  SageMaker training job name
        target:    Model slot to update — "best" or "final"
    """
    from app.services.insurance_model_service import insurance_model_service
    import asyncio

    try:
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None,
            lambda: insurance_model_service.load_from_sagemaker_job(job_name, target=target)
        )

        if success:
            config = insurance_model_service._config
            return {
                "success": True,
                "message": f"Model loaded from SageMaker job '{job_name}' into '{target}' slot",
                "model_available": insurance_model_service.is_available,
                "config": {
                    "base_model": config.get("base_model"),
                    "num_clause_labels": config.get("num_clause_labels"),
                    "num_intent_labels": config.get("num_intent_labels"),
                },
            }
        else:
            return {
                "success": False,
                "message": f"Failed to load model from job '{job_name}'. "
                           "Check that the job is completed and AWS credentials are valid.",
                "model_available": insurance_model_service.is_available,
            }
    except Exception as e:
        _admin_logger.error(f"ML SageMaker load failed: {e}")
        raise HTTPException(status_code=500, detail=f"ML load error: {str(e)}")
