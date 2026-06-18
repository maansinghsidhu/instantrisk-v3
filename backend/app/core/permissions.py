"""
InstantRisk V3 - Permission Utilities

This module provides utilities and FastAPI dependencies for permission checking
that can be used across the application to protect routes.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable, List, Optional, Union
from fastapi import Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.rbac import (
    Permission, Role, Team, TeamMembership, UserPermissionCache
)

# 5 minutes — matches runbook W3-36; closes audit D4.13.
# Hardcoded to avoid expanding the config surface; promote to settings only
# if a deployment needs to tune it.
PERMISSION_CACHE_TTL_SECONDS = 5 * 60


async def get_user_permissions(
    user: User,
    db: AsyncSession
) -> set:
    """
    Get all effective permissions for a user.

    Args:
        user: The user to get permissions for.
        db: Database session.

    Returns:
        set: Set of permission names the user has.
    """
    # Admins have all permissions
    if user.role == UserRole.ADMIN:
        result = await db.execute(
            select(Permission).where(Permission.is_active == True)
        )
        all_perms = result.scalars().all()
        return {p.name for p in all_perms}

    # Get permissions through team memberships
    permissions = set()

    result = await db.execute(
        select(TeamMembership)
        .options(
            selectinload(TeamMembership.role).selectinload(Role.permissions)
        )
        .where(
            and_(
                TeamMembership.user_id == user.id,
                TeamMembership.is_active == True
            )
        )
    )
    memberships = result.scalars().all()

    for m in memberships:
        if m.role and m.role.permissions:
            for perm in m.role.permissions:
                if perm.is_active:
                    permissions.add(perm.name)

    return permissions


async def check_permission(
    user: User,
    permission_name: str,
    db: AsyncSession
) -> bool:
    """
    Check if a user has a specific permission.

    Args:
        user: The user to check.
        permission_name: The permission to check for (e.g., "assessment:write").
        db: Database session.

    Returns:
        bool: True if user has the permission, False otherwise.
    """
    # Admins have all permissions
    if user.role == UserRole.ADMIN:
        return True

    # Check permission cache first, honouring TTL.
    # Rows older than PERMISSION_CACHE_TTL_SECONDS are treated as misses so
    # that stale grants (e.g. after a user is removed from a team) lose
    # force on the very next call, not the next deploy. See audit D4.13.
    _cache_cutoff = datetime.now(timezone.utc) - timedelta(seconds=PERMISSION_CACHE_TTL_SECONDS)
    cache_result = await db.execute(
        select(UserPermissionCache).where(
            and_(
                UserPermissionCache.user_id == user.id,
                UserPermissionCache.permission_name == permission_name,
                UserPermissionCache.cached_at > _cache_cutoff,
            )
        )
    )
    if cache_result.scalar_one_or_none():
        return True

    # Check through team memberships
    result = await db.execute(
        select(TeamMembership)
        .options(
            selectinload(TeamMembership.role).selectinload(Role.permissions)
        )
        .where(
            and_(
                TeamMembership.user_id == user.id,
                TeamMembership.is_active == True
            )
        )
    )
    memberships = result.scalars().all()

    for m in memberships:
        if m.role and m.role.permissions:
            for perm in m.role.permissions:
                if perm.name == permission_name and perm.is_active:
                    return True

    return False


async def check_any_permission(
    user: User,
    permission_names: List[str],
    db: AsyncSession
) -> bool:
    """
    Check if a user has any of the specified permissions.

    Args:
        user: The user to check.
        permission_names: List of permissions to check for.
        db: Database session.

    Returns:
        bool: True if user has at least one permission, False otherwise.
    """
    if user.role == UserRole.ADMIN:
        return True

    for perm in permission_names:
        if await check_permission(user, perm, db):
            return True
    return False


async def check_all_permissions(
    user: User,
    permission_names: List[str],
    db: AsyncSession
) -> bool:
    """
    Check if a user has all of the specified permissions.

    Args:
        user: The user to check.
        permission_names: List of permissions to check for.
        db: Database session.

    Returns:
        bool: True if user has all permissions, False otherwise.
    """
    if user.role == UserRole.ADMIN:
        return True

    for perm in permission_names:
        if not await check_permission(user, perm, db):
            return False
    return True


async def is_team_member(
    user: User,
    team_id: int,
    db: AsyncSession
) -> bool:
    """
    Check if a user is a member of a specific team.

    Args:
        user: The user to check.
        team_id: The team ID.
        db: Database session.

    Returns:
        bool: True if user is an active member, False otherwise.
    """
    result = await db.execute(
        select(TeamMembership).where(
            and_(
                TeamMembership.user_id == user.id,
                TeamMembership.team_id == team_id,
                TeamMembership.is_active == True
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def is_team_lead(
    user: User,
    team_id: int,
    db: AsyncSession
) -> bool:
    """
    Check if a user is a team lead of a specific team.

    Args:
        user: The user to check.
        team_id: The team ID.
        db: Database session.

    Returns:
        bool: True if user is a team lead, False otherwise.
    """
    result = await db.execute(
        select(TeamMembership).where(
            and_(
                TeamMembership.user_id == user.id,
                TeamMembership.team_id == team_id,
                TeamMembership.is_team_lead == True,
                TeamMembership.is_active == True
            )
        )
    )
    return result.scalar_one_or_none() is not None


def require_permission(permission_name: str) -> Callable:
    """
    Dependency factory for requiring a specific permission.

    Usage:
        @router.get("/assessments")
        async def get_assessments(
            user: User = Depends(require_permission("assessment:read"))
        ):
            ...

    Args:
        permission_name: The permission required (e.g., "assessment:read").

    Returns:
        Callable: A FastAPI dependency function.
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        has_perm = await check_permission(current_user, permission_name, db)
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: {permission_name}"
            )
        return current_user

    return permission_checker


def require_any_permission(*permission_names: str) -> Callable:
    """
    Dependency factory for requiring any of the specified permissions.

    Usage:
        @router.get("/reports")
        async def get_reports(
            user: User = Depends(require_any_permission("report:read", "assessment:read"))
        ):
            ...

    Args:
        permission_names: The permissions, any of which grants access.

    Returns:
        Callable: A FastAPI dependency function.
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        has_perm = await check_any_permission(current_user, list(permission_names), db)
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required one of: {', '.join(permission_names)}"
            )
        return current_user

    return permission_checker


def require_all_permissions(*permission_names: str) -> Callable:
    """
    Dependency factory for requiring all of the specified permissions.

    Usage:
        @router.post("/assessments/{id}/approve")
        async def approve_assessment(
            user: User = Depends(require_all_permissions("assessment:read", "assessment:approve"))
        ):
            ...

    Args:
        permission_names: All permissions that are required.

    Returns:
        Callable: A FastAPI dependency function.
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        has_perm = await check_all_permissions(current_user, list(permission_names), db)
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required all of: {', '.join(permission_names)}"
            )
        return current_user

    return permission_checker


async def refresh_user_permission_cache(
    user_id: str,
    db: AsyncSession
) -> None:
    """
    Refresh the permission cache for a user.

    This should be called when:
    - User's team membership changes
    - Role permissions are updated
    - User is added/removed from a team

    Args:
        user_id: The user ID to refresh cache for.
        db: Database session.
    """
    from sqlalchemy import delete

    # Clear existing cache
    await db.execute(
        delete(UserPermissionCache).where(
            UserPermissionCache.user_id == user_id
        )
    )

    # Get user
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        return

    # Get all permissions through team memberships
    result = await db.execute(
        select(TeamMembership)
        .options(
            selectinload(TeamMembership.role).selectinload(Role.permissions)
        )
        .where(
            and_(
                TeamMembership.user_id == user_id,
                TeamMembership.is_active == True
            )
        )
    )
    memberships = result.scalars().all()

    # Build cache entries
    for m in memberships:
        if m.role and m.role.permissions:
            for perm in m.role.permissions:
                if perm.is_active:
                    cache_entry = UserPermissionCache(
                        user_id=user_id,
                        permission_name=perm.name,
                        source_team_id=m.team_id,
                        source_role_id=m.role_id
                    )
                    db.add(cache_entry)

    await db.commit()


async def clear_user_permission_cache(user_id, db: AsyncSession) -> int:
    """
    Delete every `UserPermissionCache` row for `user_id`.

    Use after any change that affects a single user's effective permissions:
    add/remove/soft-delete team membership, change of role on a membership,
    or any future per-user override. The next `check_permission` call
    re-derives from `team_memberships` and re-warms the cache.

    Args:
        user_id: The user whose cache should be wiped.
        db: Database session.

    Returns:
        Number of cache rows deleted (0 if the user had no cached rows).
    """
    from sqlalchemy import delete

    result = await db.execute(
        delete(UserPermissionCache).where(UserPermissionCache.user_id == user_id)
    )
    await db.commit()
    return result.rowcount or 0


async def clear_permission_cache_for_role(role_id, db: AsyncSession) -> int:
    """
    Delete `UserPermissionCache` rows for every user holding `role_id`.

    Use after a role's permission set changes (a permission was added or
    revoked from the role, the role's `is_active` flag flipped, etc.) so
    every holder re-derives on the next call.

    Args:
        role_id: The role whose holders' caches should be wiped.
        db: Database session.

    Returns:
        Number of cache rows deleted across all holders (0 if no active
        holder or no rows were cached).
    """
    from sqlalchemy import delete, select

    user_ids_result = await db.execute(
        select(TeamMembership.user_id).where(
            and_(
                TeamMembership.role_id == role_id,
                TeamMembership.is_active == True,  # noqa: E712
            )
        )
    )
    user_ids = [row[0] for row in user_ids_result.all()]
    if not user_ids:
        return 0

    result = await db.execute(
        delete(UserPermissionCache).where(UserPermissionCache.user_id.in_(user_ids))
    )
    await db.commit()
    return result.rowcount or 0


async def clear_all_permission_cache(db: AsyncSession) -> None:
    """
    Clear all permission cache entries.

    Useful when roles or permissions are modified globally.

    Args:
        db: Database session.
    """
    from sqlalchemy import delete

    await db.execute(delete(UserPermissionCache))
    await db.commit()


# =============================================================================
# Convenience Dependencies
# =============================================================================

# Assessment permissions
require_assessment_read = require_permission("assessment:read")
require_assessment_write = require_permission("assessment:write")
require_assessment_approve = require_permission("assessment:approve")
require_assessment_delete = require_permission("assessment:delete")

# Placement permissions
require_placement_read = require_permission("placement:read")
require_placement_write = require_permission("placement:write")
require_placement_approve = require_permission("placement:approve")

# Exposure permissions
require_exposure_read = require_permission("exposure:read")
require_exposure_write = require_permission("exposure:write")

# Compliance permissions
require_compliance_read = require_permission("compliance:read")
require_compliance_submit = require_permission("compliance:submit")
require_compliance_manage = require_permission("compliance:manage")

# Pricing/Quote permissions
require_pricing_read = require_permission("pricing:read")
require_pricing_write = require_permission("pricing:write")
require_quote_read = require_permission("quote:read")
require_quote_write = require_permission("quote:write")
require_quote_approve = require_permission("quote:approve")

# Claims permissions
require_claims_read = require_permission("claims:read")
require_claims_write = require_permission("claims:write")
require_claims_approve = require_permission("claims:approve")

# Document permissions
require_document_read = require_permission("document:read")
require_document_write = require_permission("document:write")
require_document_delete = require_permission("document:delete")

# Report permissions
require_report_read = require_permission("report:read")
require_report_write = require_permission("report:write")

# Team/User management permissions
require_team_manage = require_permission("team:manage")
require_team_read = require_permission("team:read")
require_user_manage = require_permission("user:manage")
require_user_read = require_permission("user:read")

# Integration permissions
require_integration_read = require_permission("integration:read")
require_integration_manage = require_permission("integration:manage")

# Audit permissions
require_audit_read = require_permission("audit:read")
