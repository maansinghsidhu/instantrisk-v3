"""
InstantRisk V2 - Subscription Router

API endpoints for managing user subscriptions and feature access.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from app.models.feature_limits import (
    TIER_LIMITS,
    FEATURE_DESCRIPTIONS,
    get_tier_limits,
    get_feature_access,
    get_allowed_analysis_modes
)

router = APIRouter(prefix="/subscription", tags=["subscription"])


# Pydantic schemas
class SubscriptionResponse(BaseModel):
    """Response schema for subscription details."""
    id: int
    tier: str
    status: str
    started_at: Optional[datetime]
    expires_at: Optional[datetime]
    monthly_assessments_used: int
    monthly_documents_generated: int
    monthly_chat_messages_used: int

    class Config:
        from_attributes = True


class SubscriptionLimitsResponse(BaseModel):
    """Response schema for subscription limits."""
    tier: str
    limits: dict
    usage: dict
    remaining: dict


class FeatureAccessResponse(BaseModel):
    """Response schema for feature access."""
    feature_name: str
    has_access: bool
    description: Optional[str]
    required_tier: str


class AllFeaturesResponse(BaseModel):
    """Response schema for all features."""
    tier: str
    features: dict
    analysis_modes: list


class UpgradeRequestResponse(BaseModel):
    """Response schema for upgrade request."""
    message: str
    current_tier: str
    requested_tier: str
    upgrade_url: Optional[str]


@router.get("", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's subscription details.

    Returns subscription tier, status, and usage information.
    """
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        # Create default trial subscription
        subscription = Subscription(
            user_id=current_user.id,
            tier=SubscriptionTier.TRIAL,
            status=SubscriptionStatus.ACTIVE,
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=14)
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

    return SubscriptionResponse(
        id=subscription.id,
        tier=subscription.tier.value,
        status=subscription.status.value,
        started_at=subscription.started_at,
        expires_at=subscription.expires_at,
        monthly_assessments_used=subscription.monthly_assessments_used,
        monthly_documents_generated=subscription.monthly_documents_generated,
        monthly_chat_messages_used=subscription.monthly_chat_messages_used
    )


@router.get("/limits", response_model=SubscriptionLimitsResponse)
async def get_subscription_limits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get subscription limits and current usage.

    Returns the limits for the user's tier, current usage, and remaining quotas.
    """
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()

    tier = subscription.tier if subscription else SubscriptionTier.TRIAL
    tier_limits = get_tier_limits(tier)

    usage = {
        "monthly_assessments": subscription.monthly_assessments_used if subscription else 0,
        "monthly_documents": subscription.monthly_documents_generated if subscription else 0,
        "monthly_chat_messages": subscription.monthly_chat_messages_used if subscription else 0,
    }

    remaining = {
        "monthly_assessments": max(0, tier_limits.get("monthly_assessments", 0) - usage["monthly_assessments"]),
        "monthly_documents": max(0, tier_limits.get("monthly_documents", 0) - usage["monthly_documents"]),
        "monthly_chat_messages": max(0, tier_limits.get("monthly_chat_messages", 0) - usage["monthly_chat_messages"]),
    }

    return SubscriptionLimitsResponse(
        tier=tier.value,
        limits={
            "monthly_assessments": tier_limits.get("monthly_assessments", 0),
            "monthly_documents": tier_limits.get("monthly_documents", 0),
            "monthly_chat_messages": tier_limits.get("monthly_chat_messages", 0),
            "storage_gb": tier_limits.get("storage_gb", 0),
        },
        usage=usage,
        remaining=remaining
    )


@router.get("/features", response_model=AllFeaturesResponse)
async def get_all_features(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all features and their access status for the current user.

    Returns a complete list of features with access status and descriptions.
    """
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()

    tier = subscription.tier if subscription else SubscriptionTier.TRIAL
    tier_limits = get_tier_limits(tier)

    features = {}
    for feature_name, has_access in tier_limits.get("features", {}).items():
        feature_info = FEATURE_DESCRIPTIONS.get(feature_name, {})
        features[feature_name] = {
            "has_access": has_access,
            "name": feature_info.get("name", feature_name),
            "description": feature_info.get("description", ""),
            "icon": feature_info.get("icon", ""),
        }

    return AllFeaturesResponse(
        tier=tier.value,
        features=features,
        analysis_modes=get_allowed_analysis_modes(tier)
    )


@router.get("/features/{feature_name}", response_model=FeatureAccessResponse)
async def check_feature_access(
    feature_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check if user has access to a specific feature.

    Args:
        feature_name: The name of the feature to check (e.g., 'claimsense_chat')
    """
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()

    tier = subscription.tier if subscription else SubscriptionTier.TRIAL
    has_access = get_feature_access(tier, feature_name)

    # Determine required tier for the feature
    required_tier = "basic"
    for check_tier in [SubscriptionTier.BASIC, SubscriptionTier.PREMIUM]:
        if get_feature_access(check_tier, feature_name):
            required_tier = check_tier.value
            break

    feature_info = FEATURE_DESCRIPTIONS.get(feature_name, {})

    return FeatureAccessResponse(
        feature_name=feature_name,
        has_access=has_access,
        description=feature_info.get("description"),
        required_tier=required_tier
    )


@router.post("/upgrade", response_model=UpgradeRequestResponse)
async def request_upgrade(
    target_tier: str = "premium",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Request a subscription upgrade.

    In production, this would redirect to a payment flow.
    For now, it records the upgrade request.
    """
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()

    current_tier = subscription.tier.value if subscription else "trial"

    # Validate target tier
    valid_tiers = ["basic", "premium"]
    if target_tier not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier. Valid options: {', '.join(valid_tiers)}"
        )

    # Check if already at or above requested tier
    tier_order = {"trial": 0, "basic": 1, "premium": 2}
    if tier_order.get(current_tier, 0) >= tier_order.get(target_tier, 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You already have {current_tier} tier which is equal to or higher than {target_tier}"
        )

    # In production, this would create a checkout session with Stripe
    # For now, return information about the upgrade

    return UpgradeRequestResponse(
        message=f"To upgrade to {target_tier}, please contact our sales team or visit the upgrade page.",
        current_tier=current_tier,
        requested_tier=target_tier,
        upgrade_url="/settings/subscription"  # Frontend route
    )


@router.post("/increment-usage/{usage_type}")
async def increment_usage(
    usage_type: str,
    amount: int = 1,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Increment usage counter for a resource type.

    This endpoint is used internally by other services to track usage.

    Args:
        usage_type: One of 'assessments', 'documents', 'chat_messages'
        amount: Amount to increment (default: 1)
    """
    valid_types = ["assessments", "documents", "chat_messages"]
    if usage_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid usage type. Valid options: {', '.join(valid_types)}"
        )

    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found"
        )

    subscription.increment_usage(usage_type, amount)
    await db.commit()

    return {"message": f"Usage incremented", "type": usage_type, "amount": amount}
