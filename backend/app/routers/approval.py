"""
InstantRisk V2 - Approval Router

API endpoints for managing user account approvals (admin only).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, ApprovalStatus, UserRole
from app.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus

router = APIRouter(prefix="/admin", tags=["admin"])


# Pydantic schemas
class PendingUserResponse(BaseModel):
    """Response schema for pending user."""

    id: int
    email: str
    full_name: str
    role: str
    created_at: datetime
    syndicate_id: Optional[int]

    class Config:
        from_attributes = True


class ApprovalResponse(BaseModel):
    """Response schema for approval action."""

    message: str
    user_id: str
    email: str
    approval_status: str


class RejectRequest(BaseModel):
    """Request schema for rejecting a user."""

    reason: str


class ApprovalStatusResponse(BaseModel):
    """Response schema for checking approval status."""

    status: str
    message: str
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]


def require_admin_role(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that ensures user is an admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires admin privileges",
        )
    return current_user


@router.get("/pending-approvals", response_model=List[PendingUserResponse])
async def get_pending_approvals(
    current_user: User = Depends(require_admin_role), db: AsyncSession = Depends(get_db)
):
    """
    Get list of users pending approval.

    Admin only endpoint.
    """
    result = await db.execute(
        select(User).where(User.approval_status == ApprovalStatus.PENDING)
    )
    pending_users = result.scalars().all()

    return [
        PendingUserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            created_at=user.created_at,
            syndicate_id=user.syndicate_id,
        )
        for user in pending_users
    ]


@router.post("/approve/{user_id}", response_model=ApprovalResponse)
async def approve_user(
    user_id: str,
    subscription_tier: str = "basic",
    current_user: User = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a pending user account.

    Admin only endpoint.

    Args:
        user_id: ID of the user to approve
        subscription_tier: Tier to assign (default: 'basic')
    """
    # Validate subscription tier
    valid_tiers = {
        "trial": SubscriptionTier.TRIAL,
        "basic": SubscriptionTier.BASIC,
        "premium": SubscriptionTier.PREMIUM,
    }
    if subscription_tier not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier. Valid options: {', '.join(valid_tiers.keys())}",
        )

    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.approval_status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is already {user.approval_status.value}",
        )

    # Approve user
    user.approval_status = ApprovalStatus.APPROVED
    user.approved_by = current_user.id
    user.approved_at = datetime.now(timezone.utc)
    user.is_active = True

    # Check if subscription already exists
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    existing_subscription = sub_result.scalar_one_or_none()

    if existing_subscription:
        # Update existing subscription
        existing_subscription.tier = valid_tiers[subscription_tier]
        existing_subscription.status = SubscriptionStatus.ACTIVE
        existing_subscription.started_at = datetime.now(timezone.utc)
        existing_subscription.expires_at = datetime.now(timezone.utc) + timedelta(
            days=365
        )
    else:
        # Create subscription for user
        subscription = Subscription(
            user_id=user_id,
            tier=valid_tiers[subscription_tier],
            status=SubscriptionStatus.ACTIVE,
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=365),  # 1 year subscription
        )
        db.add(subscription)

    await db.commit()

    return ApprovalResponse(
        message=f"User approved successfully with {subscription_tier} subscription",
        user_id=user_id,
        email=user.email,
        approval_status="approved",
    )


@router.post("/reject/{user_id}", response_model=ApprovalResponse)
async def reject_user(
    user_id: str,
    reject_request: RejectRequest,
    current_user: User = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a pending user account.

    Admin only endpoint.

    Args:
        user_id: ID of the user to reject
        reject_request: Contains the rejection reason
    """
    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.approval_status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is already {user.approval_status.value}",
        )

    # Reject user
    user.approval_status = ApprovalStatus.REJECTED
    user.approved_by = current_user.id
    user.approved_at = datetime.now(timezone.utc)
    user.rejection_reason = reject_request.reason
    user.is_active = False

    await db.commit()

    return ApprovalResponse(
        message="User rejected",
        user_id=user_id,
        email=user.email,
        approval_status="rejected",
    )


@router.get("/users", response_model=List[dict])
async def get_all_users(
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all users with optional status filter and email search.

    Admin only endpoint.

    Args:
        status_filter: Filter by approval status ('pending', 'approved', 'rejected')
        search: Case-insensitive search term matched against email and full_name
    """
    query = select(User)

    conditions = []
    if status_filter:
        status_map = {
            "pending": ApprovalStatus.PENDING,
            "approved": ApprovalStatus.APPROVED,
            "rejected": ApprovalStatus.REJECTED,
        }
        if status_filter in status_map:
            conditions.append(User.approval_status == status_map[status_filter])

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                User.email.ilike(term),
                User.full_name.ilike(term),
            )
        )

    if conditions:
        query = query.where(and_(*conditions))

    result = await db.execute(query)
    users = result.scalars().all()

    return [
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "approval_status": user.approval_status.value,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "approved_at": user.approved_at.isoformat() if user.approved_at else None,
        }
        for user in users
    ]


# Non-admin endpoint for users to check their own approval status
approval_status_router = APIRouter(prefix="/approval", tags=["approval"])


@approval_status_router.get("/status", response_model=ApprovalStatusResponse)
async def check_approval_status(
    current_user: User = Depends(get_current_user),
):
    """
    Check the approval status of the current user's account.

    Returns the approval status and any relevant messages.
    """
    messages = {
        ApprovalStatus.PENDING: "Your account is pending admin approval. You will be notified once approved.",
        ApprovalStatus.APPROVED: "Your account has been approved. You have full access to the platform.",
        ApprovalStatus.REJECTED: f"Your account registration was rejected. Reason: {current_user.rejection_reason or 'No reason provided'}",
    }

    return ApprovalStatusResponse(
        status=current_user.approval_status.value,
        message=messages.get(current_user.approval_status, "Unknown status"),
        approved_at=current_user.approved_at,
        rejection_reason=current_user.rejection_reason,
    )
