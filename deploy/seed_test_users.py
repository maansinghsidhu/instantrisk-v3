"""
Seed test users with different subscription tiers.
This script creates users for TRIAL, BASIC, and PREMIUM tiers.

Run this via ECS Exec or include in startup to seed test data.
"""
import asyncio
import sys
import os

# Add the backend path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def seed_users():
    """Create test users with different subscription tiers."""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, text
    from passlib.context import CryptContext

    # Password hashing
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # Database connection using environment variables
    import os
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Get database URL from environment
    db_host = os.environ.get('DATABASE_HOST', os.environ.get('POSTGRES_HOST', 'localhost'))
    db_port = os.environ.get('DATABASE_PORT', os.environ.get('POSTGRES_PORT', '5432'))
    db_name = os.environ.get('DATABASE_NAME', os.environ.get('POSTGRES_DB', 'instantrisk'))
    db_user = os.environ.get('DATABASE_USER', os.environ.get('POSTGRES_USER', 'instantrisk_admin'))
    db_pass = os.environ.get('DATABASE_PASSWORD', os.environ.get('POSTGRES_PASSWORD', ''))

    database_url = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    print(f"Connecting to database at {db_host}:{db_port}/{db_name}...")

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Test users to create
    test_users = [
        {
            "email": "trial@instantrisk.com",
            "password": "Trial2026pass",
            "full_name": "Trial User",
            "role": "broker",
            "tier": "trial",
            "expires_days": 14,
        },
        {
            "email": "basic@instantrisk.com",
            "password": "Basic2026pass",
            "full_name": "Basic User",
            "role": "broker",
            "tier": "basic",
            "expires_days": 365,
        },
        {
            "email": "premium@instantrisk.com",
            "password": "Premium2026pass",
            "full_name": "Premium User",
            "role": "broker",
            "tier": "premium",
            "expires_days": 365,
        },
    ]

    async with async_session() as session:
        for user_data in test_users:
            # Check if user exists
            result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": user_data["email"]}
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"User {user_data['email']} already exists (id={existing})")
                # Update subscription tier
                await session.execute(
                    text("""
                        UPDATE subscriptions
                        SET tier = :tier, status = 'active',
                            expires_at = NOW() + INTERVAL ':days days'
                        WHERE user_id = :user_id
                    """.replace(":days", str(user_data["expires_days"]))),
                    {"tier": user_data["tier"], "user_id": existing}
                )
                print(f"  Updated subscription to {user_data['tier']}")
                continue

            # Hash password
            hashed_pw = pwd_context.hash(user_data["password"][:72])

            # Insert user
            result = await session.execute(
                text("""
                    INSERT INTO users (email, hashed_password, full_name, role,
                                       is_active, is_verified, approval_status, created_at, updated_at)
                    VALUES (:email, :hashed_password, :full_name, :role,
                            true, true, 'approved', NOW(), NOW())
                    RETURNING id
                """),
                {
                    "email": user_data["email"],
                    "hashed_password": hashed_pw,
                    "full_name": user_data["full_name"],
                    "role": user_data["role"],
                }
            )
            user_id = result.scalar_one()
            print(f"Created user {user_data['email']} (id={user_id})")

            # Insert subscription
            await session.execute(
                text("""
                    INSERT INTO subscriptions (user_id, tier, status, started_at, expires_at, created_at, updated_at)
                    VALUES (:user_id, :tier, 'active', NOW(), NOW() + INTERVAL ':days days', NOW(), NOW())
                """.replace(":days", str(user_data["expires_days"]))),
                {"user_id": user_id, "tier": user_data["tier"]}
            )
            print(f"  Created {user_data['tier']} subscription")

        await session.commit()
        print("\nTest users seeded successfully!")

    # List all users
    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT u.email, u.role, s.tier, s.status
                FROM users u
                LEFT JOIN subscriptions s ON u.id = s.user_id
                ORDER BY u.email
            """)
        )
        rows = result.fetchall()
        print("\n=== All Users ===")
        for row in rows:
            print(f"  {row[0]} | role={row[1]} | tier={row[2]} | status={row[3]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_users())
