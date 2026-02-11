"""
TEMPORARY Admin Reset Router - DELETE AFTER USE

Provides endpoints for database reset operations.
Protected by admin secret key.
"""

import uuid
import bcrypt
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.core.database import engine

router = APIRouter(prefix="/admin", tags=["Admin Reset"])

# Secret key for admin operations - DELETE THIS ROUTER AFTER USE
ADMIN_SECRET = "InstantRisk2026Reset!"


@router.post("/reset-database")
async def reset_database(
    secret: str = Query(..., description="Admin secret key"),
):
    """
    DANGEROUS: Resets the entire database and recreates demo users.

    This endpoint will:
    1. Delete all data from tables
    2. Delete all users
    3. Create 3 demo users (trial, basic, premium)

    Args:
        secret: Must match ADMIN_SECRET
    """
    if secret != ADMIN_SECRET:
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
        raise HTTPException(500, f"Failed to create demo users: {str(e)}")

    return {
        "status": "success",
        "message": "Database reset complete",
        "results": results,
        "demo_accounts": [
            {"email": "trial@instantrisk.com", "password": "Demo2026pass", "tier": "trial"},
            {"email": "basic@instantrisk.com", "password": "Demo2026pass", "tier": "basic"},
            {"email": "demo@instantrisk.com", "password": "Demo2026pass", "tier": "premium"}
        ]
    }


@router.get("/verify")
async def verify_reset():
    """Verify database state after reset."""
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
        raise HTTPException(500, str(e))
