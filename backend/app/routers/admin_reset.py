"""
Admin Reset Router

Provides endpoints for database reset operations.
Protected by admin secret key from environment.
"""

import os
import uuid
import bcrypt
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import text

from app.core.database import engine
from app.core.security import get_current_admin_user
from app.models.user import User
from app.config import settings

router = APIRouter(prefix="/admin", tags=["Admin Reset"])

_reset_logger = logging.getLogger("security.admin_reset")

# Admin secret from environment variable
ADMIN_SECRET = os.environ.get("ADMIN_RESET_SECRET", settings.SECRET_KEY or "change-me-in-production")


@router.post("/reset-database")
async def reset_database(
    secret: str = Query(..., description="Admin secret key"),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Reset the database and recreate demo users.

    Requires admin authentication AND admin secret key.
    """
    if secret != ADMIN_SECRET:
        _reset_logger.warning(f"Invalid reset secret attempt by user {current_user.id}")
        raise HTTPException(403, "Invalid admin secret")

    results = []

    # Delete in order respecting FK constraints
    delete_tables = [
        "chat_messages",
        "documents",
        "upload_sessions",
        "generated_documents",
        "sanctions_screenings",
        "assessments",
        "templates",
        "reference_documents",
        "subscriptions",
        "users",
    ]

    # Use separate transactions for each table to avoid cascading failures
    for table_name in delete_tables:
        try:
            async with engine.begin() as conn:
                try:
                    # Try TRUNCATE CASCADE first (faster, resets sequences)
                    await conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
                    results.append(f"Truncated {table_name}")
                except Exception:
                    # Rollback is automatic, start fresh transaction for DELETE
                    pass
        except Exception:
            pass

        # If TRUNCATE failed, try DELETE in a new transaction
        if not any(table_name in r for r in results):
            try:
                async with engine.begin() as conn:
                    result = await conn.execute(text(f"DELETE FROM {table_name}"))
                    results.append(f"Deleted {table_name}: {result.rowcount} rows")
            except Exception as e:
                results.append(f"Skip {table_name}: {str(e)[:50]}")

    # Create demo users with fresh connection
    try:
        password_hash = bcrypt.hashpw(b"Demo2026pass", bcrypt.gensalt()).decode()
        now = datetime.utcnow()

        demo_users = [
            ("trial@instantrisk.com", "Trial User", "trial"),
            ("basic@instantrisk.com", "Basic User", "basic"),
            ("demo@instantrisk.com", "Premium User", "premium")
        ]

        async with engine.begin() as conn:
            for email, name, tier in demo_users:
                user_id = str(uuid.uuid4())

                await conn.execute(text("""
                    INSERT INTO users (id, email, hashed_password, full_name, role,
                        is_active, is_verified, approval_status, preferred_language,
                        created_at, updated_at)
                    VALUES (:id, :email, :password, :name, 'underwriter',
                        true, true, 'approved', 'en', :now, :now)
                """), {
                    "id": user_id,
                    "email": email,
                    "password": password_hash,
                    "name": name,
                    "now": now
                })

                await conn.execute(text("""
                    INSERT INTO subscriptions (user_id, tier, status, started_at,
                        monthly_assessments_used, created_at, updated_at)
                    VALUES (:user_id, :tier, 'active', :now, 0, :now, :now)
                """), {
                    "user_id": user_id,
                    "tier": tier,
                    "now": now
                })

                results.append(f"Created {email} ({tier} tier)")

    except Exception as e:
        _reset_logger.error(f"Failed to create demo users: {e}")
        raise HTTPException(500, "User creation failed")

    _reset_logger.info(f"Database reset by admin user {current_user.id}")
    return {
        "status": "success",
        "message": "Database reset complete",
        "results": results,
        "demo_accounts": [
            {"email": "trial@instantrisk.com", "tier": "trial"},
            {"email": "basic@instantrisk.com", "tier": "basic"},
            {"email": "demo@instantrisk.com", "tier": "premium"}
        ]
    }


@router.get("/verify")
async def verify_reset(
    current_user: User = Depends(get_current_admin_user),
):
    """Verify database state after reset (admin only)."""
    try:
        async with engine.begin() as conn:
            user_count = await conn.execute(text("SELECT COUNT(*) FROM users"))
            assessment_count = await conn.execute(text("SELECT COUNT(*) FROM assessments"))
            sub_count = await conn.execute(text("SELECT COUNT(*) FROM subscriptions"))

            return {
                "users": user_count.scalar(),
                "assessments": assessment_count.scalar(),
                "subscriptions": sub_count.scalar()
            }
    except Exception as e:
        _reset_logger.error(f"Verify failed: {e}")
        raise HTTPException(500, "Verification failed")
