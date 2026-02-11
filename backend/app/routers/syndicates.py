"""
InstantRisk V2 - Syndicates Router

API endpoints for managing Lloyd's syndicates.
Used by the Lloyd's Admin Dashboard for market oversight and syndicate management.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.syndicate import Syndicate
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.syndicate import (
    SyndicateCreate,
    SyndicateUpdate,
    SyndicateResponse,
    SyndicateListResponse,
    SyndicateUserResponse,
    SyndicateUsersListResponse,
)

router = APIRouter()


# =============================================================================
# Helper Functions
# =============================================================================

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role for access."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def get_syndicate_by_id(
    syndicate_id: int,
    db: AsyncSession,
    include_relationships: bool = False
) -> Syndicate:
    """Get a syndicate by ID or raise 404."""
    if include_relationships:
        result = await db.execute(
            select(Syndicate)
            .options(selectinload(Syndicate.users))
            .where(Syndicate.id == syndicate_id)
        )
    else:
        result = await db.execute(
            select(Syndicate).where(Syndicate.id == syndicate_id)
        )

    syndicate = result.scalar_one_or_none()
    if not syndicate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Syndicate with ID {syndicate_id} not found"
        )
    return syndicate


def syndicate_to_response(syndicate: Syndicate, user_count: int = None, assessment_count: int = None) -> dict:
    """Convert Syndicate model to response dict."""
    return {
        "id": syndicate.id,
        "name": syndicate.name,
        "aiin": syndicate.aiin,
        "managing_agent": syndicate.managing_agent,
        "capacity": syndicate.capacity,
        "current_utilization": syndicate.current_utilization,
        "min_premium": syndicate.min_premium,
        "max_premium": syndicate.max_premium,
        "target_loss_ratio": syndicate.target_loss_ratio,
        "risk_appetite": syndicate.risk_appetite or {},
        "lines_of_business": syndicate.lines_of_business or [],
        "excluded_territories": syndicate.excluded_territories or [],
        "preferred_territories": syndicate.preferred_territories or [],
        "contact_email": syndicate.contact_email,
        "contact_phone": syndicate.contact_phone,
        "notes": syndicate.notes,
        "is_active": syndicate.is_active,
        "created_at": syndicate.created_at,
        "updated_at": syndicate.updated_at,
        "user_count": user_count,
        "assessment_count": assessment_count,
    }


# =============================================================================
# Syndicate CRUD Endpoints
# =============================================================================

@router.get("", response_model=SyndicateListResponse)
async def list_syndicates(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name, AIIN, or managing agent"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List all syndicates with optional filtering.

    - **skip**: Pagination offset
    - **limit**: Maximum records to return
    - **is_active**: Filter by active status
    - **search**: Search term for name, AIIN, or managing agent
    """
    # Build query
    query = select(Syndicate)
    count_query = select(func.count(Syndicate.id))

    # Apply filters
    if is_active is not None:
        query = query.where(Syndicate.is_active == is_active)
        count_query = count_query.where(Syndicate.is_active == is_active)

    if search:
        search_filter = (
            Syndicate.name.ilike(f"%{search}%") |
            Syndicate.aiin.ilike(f"%{search}%") |
            Syndicate.managing_agent.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get syndicates with pagination
    query = query.order_by(Syndicate.name).offset(skip).limit(limit)
    result = await db.execute(query)
    syndicates = result.scalars().all()

    # Get user counts for each syndicate
    syndicate_responses = []
    for syndicate in syndicates:
        # Count users
        user_count_result = await db.execute(
            select(func.count(User.id)).where(User.syndicate_id == syndicate.id)
        )
        user_count = user_count_result.scalar() or 0

        syndicate_responses.append(syndicate_to_response(syndicate, user_count=user_count))

    return {
        "syndicates": syndicate_responses,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("", response_model=SyndicateResponse, status_code=status.HTTP_201_CREATED)
async def create_syndicate(
    syndicate_data: SyndicateCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Create a new syndicate (Admin only).

    Creates a new Lloyd's syndicate with the provided details.
    The AIIN must be unique across all syndicates.
    """
    # Check if AIIN already exists
    existing = await db.execute(
        select(Syndicate).where(Syndicate.aiin == syndicate_data.aiin)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Syndicate with AIIN '{syndicate_data.aiin}' already exists"
        )

    # Create syndicate
    syndicate = Syndicate(
        name=syndicate_data.name,
        aiin=syndicate_data.aiin,
        managing_agent=syndicate_data.managing_agent,
        capacity=syndicate_data.capacity,
        current_utilization=syndicate_data.current_utilization or 0.0,
        min_premium=syndicate_data.min_premium,
        max_premium=syndicate_data.max_premium,
        target_loss_ratio=syndicate_data.target_loss_ratio or 0.65,
        risk_appetite=syndicate_data.risk_appetite or {},
        lines_of_business=syndicate_data.lines_of_business or [],
        excluded_territories=syndicate_data.excluded_territories or [],
        preferred_territories=syndicate_data.preferred_territories or [],
        contact_email=syndicate_data.contact_email,
        contact_phone=syndicate_data.contact_phone,
        notes=syndicate_data.notes,
        is_active=syndicate_data.is_active,
    )

    db.add(syndicate)
    await db.commit()
    await db.refresh(syndicate)

    return syndicate_to_response(syndicate, user_count=0, assessment_count=0)


@router.get("/{syndicate_id}", response_model=SyndicateResponse)
async def get_syndicate(
    syndicate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get a syndicate by ID.

    Returns detailed information about a specific syndicate including
    user count and assessment count.
    """
    syndicate = await get_syndicate_by_id(syndicate_id, db)

    # Count users
    user_count_result = await db.execute(
        select(func.count(User.id)).where(User.syndicate_id == syndicate.id)
    )
    user_count = user_count_result.scalar() or 0

    return syndicate_to_response(syndicate, user_count=user_count)


@router.put("/{syndicate_id}", response_model=SyndicateResponse)
async def update_syndicate(
    syndicate_id: int,
    syndicate_data: SyndicateUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Update a syndicate (Admin only).

    Updates the specified fields of an existing syndicate.
    Only provided fields will be updated.
    """
    syndicate = await get_syndicate_by_id(syndicate_id, db)

    # Update fields that are provided
    update_data = syndicate_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(syndicate, field, value)

    await db.commit()
    await db.refresh(syndicate)

    # Count users
    user_count_result = await db.execute(
        select(func.count(User.id)).where(User.syndicate_id == syndicate.id)
    )
    user_count = user_count_result.scalar() or 0

    return syndicate_to_response(syndicate, user_count=user_count)


@router.delete("/{syndicate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_syndicate(
    syndicate_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete (deactivate) a syndicate (Admin only).

    Performs a soft delete by setting is_active to False.
    The syndicate data is preserved for audit purposes.
    """
    syndicate = await get_syndicate_by_id(syndicate_id, db)

    # Soft delete
    syndicate.is_active = False
    await db.commit()


# =============================================================================
# Syndicate Users Endpoints
# =============================================================================

@router.get("/{syndicate_id}/users", response_model=SyndicateUsersListResponse)
async def list_syndicate_users(
    syndicate_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List all users belonging to a syndicate.

    Returns a paginated list of users assigned to the specified syndicate.
    """
    syndicate = await get_syndicate_by_id(syndicate_id, db)

    # Get users
    users_result = await db.execute(
        select(User)
        .where(User.syndicate_id == syndicate_id)
        .order_by(User.full_name, User.email)
        .offset(skip)
        .limit(limit)
    )
    users = users_result.scalars().all()

    # Get total count
    count_result = await db.execute(
        select(func.count(User.id)).where(User.syndicate_id == syndicate_id)
    )
    total = count_result.scalar() or 0

    user_responses = [
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if user.role else None,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
        }
        for user in users
    ]

    return {
        "users": user_responses,
        "total": total,
        "syndicate_id": syndicate.id,
        "syndicate_name": syndicate.name,
    }


@router.post("/{syndicate_id}/users/{user_id}", status_code=status.HTTP_200_OK)
async def assign_user_to_syndicate(
    syndicate_id: int,
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Assign a user to a syndicate (Admin only).

    Updates the user's syndicate_id to assign them to the specified syndicate.
    """
    syndicate = await get_syndicate_by_id(syndicate_id, db)

    # Get user
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    # Assign user to syndicate
    user.syndicate_id = syndicate_id
    await db.commit()

    return {
        "message": f"User '{user.email}' assigned to syndicate '{syndicate.name}'",
        "user_id": user.id,
        "syndicate_id": syndicate.id
    }


@router.delete("/{syndicate_id}/users/{user_id}", status_code=status.HTTP_200_OK)
async def remove_user_from_syndicate(
    syndicate_id: int,
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Remove a user from a syndicate (Admin only).

    Sets the user's syndicate_id to None, removing their syndicate association.
    """
    syndicate = await get_syndicate_by_id(syndicate_id, db)

    # Get user
    user_result = await db.execute(
        select(User).where(User.id == user_id, User.syndicate_id == syndicate_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found in syndicate {syndicate_id}"
        )

    # Remove user from syndicate
    user.syndicate_id = None
    await db.commit()

    return {
        "message": f"User '{user.email}' removed from syndicate '{syndicate.name}'",
        "user_id": user.id,
        "syndicate_id": syndicate.id
    }


# =============================================================================
# Market Statistics Endpoints
# =============================================================================

@router.get("/market/statistics")
async def get_market_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get market-wide statistics.

    Returns aggregated statistics across all active syndicates including
    total capacity, average utilization, and syndicate counts.
    """
    # Get all active syndicates
    result = await db.execute(
        select(Syndicate).where(Syndicate.is_active == True)
    )
    syndicates = result.scalars().all()

    if not syndicates:
        return {
            "total_syndicates": 0,
            "active_syndicates": 0,
            "total_capacity": 0,
            "average_utilization": 0,
            "total_users": 0,
        }

    # Calculate statistics
    total_capacity = sum(s.capacity or 0 for s in syndicates)
    utilizations = [s.current_utilization or 0 for s in syndicates if s.current_utilization is not None]
    avg_utilization = sum(utilizations) / len(utilizations) if utilizations else 0

    # Count total users across all syndicates
    user_count_result = await db.execute(
        select(func.count(User.id)).where(User.syndicate_id.isnot(None))
    )
    total_users = user_count_result.scalar() or 0

    # Count inactive syndicates
    inactive_result = await db.execute(
        select(func.count(Syndicate.id)).where(Syndicate.is_active == False)
    )
    inactive_count = inactive_result.scalar() or 0

    return {
        "total_syndicates": len(syndicates) + inactive_count,
        "active_syndicates": len(syndicates),
        "inactive_syndicates": inactive_count,
        "total_capacity": total_capacity,
        "average_utilization": round(avg_utilization, 2),
        "total_users": total_users,
        "lines_of_business": list(set(
            lob for s in syndicates
            for lob in (s.lines_of_business or [])
        )),
    }
