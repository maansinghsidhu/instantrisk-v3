"""
InstantRisk V2 - Feature Gate Middleware

This module provides dependency injection utilities for checking feature access
based on user subscription tier.
"""

from typing import Optional, Callable
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, ApprovalStatus
from app.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from app.models.feature_limits import TIER_LIMITS, get_feature_access, get_allowed_analysis_modes


async def get_user_subscription(
    db: AsyncSession,
    user_id: str
) -> Optional[Subscription]:
    """Get the subscription for a user."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Subscription:
    """
    Dependency that returns the current user's subscription.
    Creates a default TRIAL subscription if none exists.
    """
    subscription = await get_user_subscription(db, current_user.id)

    if not subscription:
        # Create default trial subscription
        subscription = Subscription(
            user_id=current_user.id,
            tier=SubscriptionTier.TRIAL,
            status=SubscriptionStatus.ACTIVE
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

    return subscription


def require_feature(feature_name: str) -> Callable:
    """
    Dependency factory that checks if user has access to a feature.

    Usage:
        @router.get("/premium-endpoint")
        async def premium_endpoint(
            current_user: User = Depends(require_feature("claimsense_chat"))
        ):
            ...
    """
    async def check_feature(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        # Admins have access to all features
        if current_user.role.value == "admin":
            return current_user

        subscription = await get_user_subscription(db, current_user.id)

        if not subscription:
            # No subscription = no premium features
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature_name}' requires an active subscription"
            )

        if not subscription.is_active():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your subscription has expired. Please renew to access this feature."
            )

        if not get_feature_access(subscription.tier, feature_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature_name}' requires a Premium subscription. Please upgrade to access this feature."
            )

        return current_user

    return check_feature


def require_analysis_mode(mode: str) -> Callable:
    """
    Dependency factory that checks if user can use a specific analysis mode.

    Usage:
        @router.post("/analyze")
        async def analyze(
            mode: str,
            current_user: User = Depends(require_analysis_mode("deep"))
        ):
            ...
    """
    async def check_mode(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        # Admins can use all modes
        if current_user.role.value == "admin":
            return current_user

        subscription = await get_user_subscription(db, current_user.id)

        if not subscription or not subscription.is_active():
            allowed_modes = ["quick"]  # Default for no subscription
        else:
            allowed_modes = get_allowed_analysis_modes(subscription.tier)

        if mode not in allowed_modes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Analysis mode '{mode}' requires a Premium subscription. Available modes: {', '.join(allowed_modes)}"
            )

        return current_user

    return check_mode


async def check_usage_limit(
    limit_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> bool:
    """
    Check if user is within usage limits for a resource type.

    Args:
        limit_type: One of 'assessments', 'documents', 'chat_messages'

    Returns:
        True if within limits, raises HTTPException otherwise
    """
    subscription = await get_user_subscription(db, current_user.id)

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active subscription found"
        )

    tier_limits = TIER_LIMITS.get(subscription.tier, TIER_LIMITS[SubscriptionTier.BASIC])

    usage_map = {
        "assessments": (subscription.monthly_assessments_used, tier_limits.get("monthly_assessments", 0)),
        "documents": (subscription.monthly_documents_generated, tier_limits.get("monthly_documents", 0)),
        "chat_messages": (subscription.monthly_chat_messages_used, tier_limits.get("monthly_chat_messages", 0)),
    }

    if limit_type not in usage_map:
        return True

    current_usage, limit = usage_map[limit_type]

    if limit > 0 and current_usage >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Monthly {limit_type.replace('_', ' ')} limit reached ({limit}). Please upgrade your subscription for more."
        )

    return True


def require_approval() -> Callable:
    """
    Dependency that ensures user account is approved.

    Usage:
        @router.get("/protected-endpoint")
        async def protected_endpoint(
            current_user: User = Depends(require_approval())
        ):
            ...
    """
    async def check_approval(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.approval_status == ApprovalStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is pending admin approval. Please wait for approval before accessing this resource."
            )

        if current_user.approval_status == ApprovalStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account registration was rejected. Please contact support for more information."
            )

        return current_user

    return check_approval


def require_admin() -> Callable:
    """
    Dependency that ensures user is an admin.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(
            current_user: User = Depends(require_admin())
        ):
            ...
    """
    async def check_admin(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role.value != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This endpoint requires admin privileges"
            )

        return current_user

    return check_admin
