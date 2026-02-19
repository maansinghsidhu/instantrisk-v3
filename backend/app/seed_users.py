"""
Seed test users with different subscription tiers.

This runs at startup to ensure test users exist in the database.
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
import uuid
import logging

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Test users to create
TEST_USERS = [
    {
        "email": "trial.user@test.com",
        "password": "TestPass123",
        "full_name": "Trial User",
        "role": "syndicate",
        "tier": "trial",
        "expires_days": 14,
    },
    {
        "email": "basic.user@test.com",
        "password": "TestPass123",
        "full_name": "Basic User",
        "role": "syndicate",
        "tier": "basic",
        "expires_days": 365,
    },
    {
        "email": "premium.user@test.com",
        "password": "TestPass123",
        "full_name": "Premium User",
        "role": "syndicate",
        "tier": "premium",
        "expires_days": 365,
    },
    {
        "email": "demo@instantrisk.com",
        "password": "Demo2026pass",
        "full_name": "Demo User",
        "role": "underwriter",
        "tier": "premium",
        "expires_days": 365,
    },
]


async def seed_test_users(session: AsyncSession) -> int:
    """
    Seed test users with different subscription tiers.

    Returns the number of users created.
    """
    created = 0

    for user_data in TEST_USERS:
        try:
            # Check if user exists
            result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": user_data["email"]}
            )
            existing = result.scalar_one_or_none()

            if existing:
                # User exists - ensure subscription exists and is correct tier
                await session.execute(
                    text("""
                        INSERT INTO subscriptions (user_id, tier, status, started_at, expires_at, created_at, updated_at)
                        VALUES (:user_id, :tier, 'active', NOW(), NOW() + INTERVAL '1 year', NOW(), NOW())
                        ON CONFLICT (user_id) DO UPDATE SET tier = :tier, status = 'active',
                            expires_at = NOW() + INTERVAL '1 year',
                            monthly_assessments_used = 0,
                            monthly_documents_generated = 0,
                            monthly_chat_messages_used = 0,
                            updated_at = NOW()
                    """),
                    {"user_id": existing, "tier": user_data["tier"]}
                )
                logger.info(f"User {user_data['email']} already exists, updated subscription to {user_data['tier']}")
                continue

            # Create new user
            user_id = uuid.uuid4()
            hashed_pw = pwd_context.hash(user_data["password"][:72])

            await session.execute(
                text("""
                    INSERT INTO users (id, email, hashed_password, full_name, role,
                                       is_active, is_verified, approval_status, created_at, updated_at)
                    VALUES (:id, :email, :hashed_password, :full_name, :role,
                            true, true, 'approved', NOW(), NOW())
                """),
                {
                    "id": user_id,
                    "email": user_data["email"],
                    "hashed_password": hashed_pw,
                    "full_name": user_data["full_name"],
                    "role": user_data["role"],
                }
            )

            # Create subscription
            await session.execute(
                text("""
                    INSERT INTO subscriptions (user_id, tier, status, started_at, expires_at, created_at, updated_at)
                    VALUES (:user_id, :tier, 'active', NOW(), NOW() + INTERVAL '1 year', NOW(), NOW())
                """),
                {"user_id": user_id, "tier": user_data["tier"]}
            )

            logger.info(f"Created user {user_data['email']} with {user_data['tier']} subscription")
            created += 1

        except Exception as e:
            logger.warning(f"Could not seed user {user_data['email']}: {e}")
            continue

    await session.commit()
    return created
