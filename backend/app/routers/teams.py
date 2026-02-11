"""
InstantRisk V3 - Teams and RBAC Router

This module provides API endpoints for team management and role-based access control:
- Team CRUD operations
- Team membership management
- Role and permission queries
- Permission checking utilities
"""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.syndicate import Syndicate
from app.models.rbac import (
    Permission, Role, Team, TeamMembership, TeamType,
    UserPermissionCache, role_permissions
)
from app.schemas.rbac import (
    # Permission schemas
    PermissionResponse,
    # Role schemas
    RoleCreate, RoleUpdate, RoleResponse, RoleListResponse,
    # Team schemas
    TeamCreate, TeamUpdate, TeamResponse, TeamDetailResponse,
    TeamListResponse, TeamMemberBrief,
    # Membership schemas
    TeamMemberAdd, TeamMemberUpdate, TeamMembershipResponse,
    TeamMembershipListResponse,
    # Permission check schemas
    UserPermissionsResponse, PermissionCheckRequest, PermissionCheckResponse,
    BulkPermissionCheckRequest, BulkPermissionCheckResponse,
)

router = APIRouter()


# =============================================================================
# Permission Checking Utilities
# =============================================================================

async def check_user_permission(
    user: User,
    permission_name: str,
    db: AsyncSession
) -> bool:
    """
    Check if a user has a specific permission.

    Admins have all permissions.
    For other users, checks team memberships and associated roles.
    """
    # Admins have all permissions
    if user.role == UserRole.ADMIN:
        return True

    # Check permission cache first (for performance)
    cache_result = await db.execute(
        select(UserPermissionCache).where(
            and_(
                UserPermissionCache.user_id == user.id,
                UserPermissionCache.permission_name == permission_name
            )
        )
    )
    if cache_result.scalar_one_or_none():
        return True

    # Check through team memberships
    result = await db.execute(
        select(TeamMembership)
        .options(selectinload(TeamMembership.role).selectinload(Role.permissions))
        .where(
            and_(
                TeamMembership.user_id == user.id,
                TeamMembership.is_active == True
            )
        )
    )
    memberships = result.scalars().all()

    for membership in memberships:
        if membership.role and membership.role.permissions:
            for perm in membership.role.permissions:
                if perm.name == permission_name and perm.is_active:
                    return True

    return False


async def require_permission(
    permission_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to require a specific permission.

    Raises HTTPException 403 if user doesn't have the permission.
    """
    has_perm = await check_user_permission(current_user, permission_name, db)
    if not has_perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied. Required: {permission_name}"
        )
    return current_user


async def require_team_manage_permission(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Require team:manage permission."""
    return await require_permission("team:manage", current_user, db)


async def require_user_manage_permission(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Require user:manage permission."""
    return await require_permission("user:manage", current_user, db)


# =============================================================================
# Permission Endpoints
# =============================================================================

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role for access."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    resource: Optional[str] = Query(None, description="Filter by resource"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: bool = Query(True, description="Filter by active status"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> List[Permission]:
    """
    List all available permissions (Admin only).

    Permissions can be filtered by resource, category, and active status.
    """
    query = select(Permission).where(Permission.is_active == is_active)

    if resource:
        query = query.where(Permission.resource == resource)
    if category:
        query = query.where(Permission.category == category)

    query = query.order_by(Permission.resource, Permission.action)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/permissions/check", response_model=PermissionCheckResponse)
async def check_permission(
    permission_name: str = Query(..., description="Permission to check (e.g., 'assessment:write')"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Check if the current user has a specific permission.

    Returns whether the permission is granted and through which role.
    """
    has_perm = await check_user_permission(current_user, permission_name, db)

    granted_via = None
    if has_perm:
        if current_user.role == UserRole.ADMIN:
            granted_via = "Role: System Admin"
        else:
            # Find which role grants the permission
            result = await db.execute(
                select(TeamMembership)
                .options(selectinload(TeamMembership.role))
                .where(
                    and_(
                        TeamMembership.user_id == current_user.id,
                        TeamMembership.is_active == True
                    )
                )
            )
            memberships = result.scalars().all()
            for m in memberships:
                if m.role and m.role.has_permission(permission_name):
                    granted_via = f"Role: {m.role.name}"
                    break

    return {
        "has_permission": has_perm,
        "permission_name": permission_name,
        "granted_via": granted_via
    }


@router.post("/permissions/check-bulk", response_model=BulkPermissionCheckResponse)
async def check_permissions_bulk(
    request: BulkPermissionCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Check multiple permissions at once.

    Useful for UI to determine which features to show/enable.
    """
    results = {}
    for perm in request.permissions:
        results[perm] = await check_user_permission(current_user, perm, db)

    return {
        "results": results,
        "all_granted": all(results.values())
    }


@router.get("/permissions/me", response_model=UserPermissionsResponse)
async def get_my_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get all effective permissions for the current user.

    Returns a comprehensive list of all permissions the user has
    through their team memberships.
    """
    permissions = set()
    teams_info = []

    if current_user.role == UserRole.ADMIN:
        # Admins have all permissions
        result = await db.execute(select(Permission).where(Permission.is_active == True))
        all_perms = result.scalars().all()
        permissions = {p.name for p in all_perms}
        teams_info = [{"name": "System Admin", "role": "Administrator"}]
    else:
        # Get permissions through team memberships
        result = await db.execute(
            select(TeamMembership)
            .options(
                selectinload(TeamMembership.role).selectinload(Role.permissions),
                selectinload(TeamMembership.team)
            )
            .where(
                and_(
                    TeamMembership.user_id == current_user.id,
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

            if m.team:
                teams_info.append({
                    "id": m.team.id,
                    "name": m.team.name,
                    "role": m.role.name if m.role else None,
                    "is_team_lead": m.is_team_lead
                })

    return {
        "user_id": current_user.id,
        "user_email": current_user.email,
        "permissions": sorted(list(permissions)),
        "teams": teams_info,
        "is_syndicate_admin": current_user.role == UserRole.ADMIN
    }


# =============================================================================
# Role Endpoints
# =============================================================================

@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    syndicate_id: Optional[int] = Query(None, description="Filter by syndicate (null for global roles)"),
    include_global: bool = Query(True, description="Include global roles"),
    is_active: bool = Query(True, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List available roles.

    Returns global roles and syndicate-specific roles.
    Non-admin users can only see roles for their own syndicate.
    """
    query = select(Role).options(selectinload(Role.permissions))

    conditions = [Role.is_active == is_active]

    # Non-admin users can only see their syndicate's roles (and global roles)
    effective_syndicate_id = syndicate_id
    if current_user.role != UserRole.ADMIN:
        effective_syndicate_id = current_user.syndicate_id

    if effective_syndicate_id:
        if include_global:
            conditions.append(
                or_(Role.syndicate_id == effective_syndicate_id, Role.syndicate_id.is_(None))
            )
        else:
            conditions.append(Role.syndicate_id == effective_syndicate_id)
    elif include_global:
        conditions.append(Role.syndicate_id.is_(None))

    query = query.where(and_(*conditions)).order_by(Role.hierarchy_level.desc(), Role.name)

    result = await db.execute(query)
    roles = result.scalars().all()

    return {
        "roles": roles,
        "total": len(roles)
    }


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user: User = Depends(require_team_manage_permission),
    db: AsyncSession = Depends(get_db)
) -> Role:
    """
    Create a new role.

    Requires team:manage permission.
    Can create syndicate-specific roles or global roles (admin only).
    """
    # Non-admins can only create syndicate-specific roles for their syndicate
    if role_data.syndicate_id is None and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create global roles"
        )

    if role_data.syndicate_id and current_user.role != UserRole.ADMIN:
        if current_user.syndicate_id != role_data.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create roles for other syndicates"
            )

    # Check for duplicate name
    existing = await db.execute(
        select(Role).where(Role.name == role_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role with name '{role_data.name}' already exists"
        )

    # Get permissions by ID or name
    permissions = []
    if role_data.permission_ids:
        perm_result = await db.execute(
            select(Permission).where(Permission.id.in_(role_data.permission_ids))
        )
        permissions.extend(perm_result.scalars().all())

    if role_data.permission_names:
        perm_result = await db.execute(
            select(Permission).where(Permission.name.in_(role_data.permission_names))
        )
        permissions.extend(perm_result.scalars().all())

    # Create role
    role = Role(
        name=role_data.name,
        description=role_data.description,
        syndicate_id=role_data.syndicate_id,
        hierarchy_level=role_data.hierarchy_level,
        is_active=role_data.is_active,
        is_system_role=False,
        permissions=list(set(permissions))  # Deduplicate
    )

    db.add(role)
    await db.commit()
    await db.refresh(role)

    return role


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Role:
    """
    Get a specific role by ID.
    """
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    return role


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    current_user: User = Depends(require_team_manage_permission),
    db: AsyncSession = Depends(get_db)
) -> Role:
    """
    Update an existing role.

    Cannot update system roles (name or delete).
    """
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    if role.is_system_role and role_data.name and role_data.name != role.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rename system roles"
        )

    # Update fields
    if role_data.name is not None:
        role.name = role_data.name
    if role_data.description is not None:
        role.description = role_data.description
    if role_data.hierarchy_level is not None:
        role.hierarchy_level = role_data.hierarchy_level
    if role_data.is_active is not None:
        role.is_active = role_data.is_active

    # Update permissions
    if role_data.permission_ids is not None or role_data.permission_names is not None:
        permissions = []
        if role_data.permission_ids:
            perm_result = await db.execute(
                select(Permission).where(Permission.id.in_(role_data.permission_ids))
            )
            permissions.extend(perm_result.scalars().all())

        if role_data.permission_names:
            perm_result = await db.execute(
                select(Permission).where(Permission.name.in_(role_data.permission_names))
            )
            permissions.extend(perm_result.scalars().all())

        role.permissions = list(set(permissions))

    await db.commit()
    await db.refresh(role)

    return role


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    current_user: User = Depends(require_team_manage_permission),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a role.

    Cannot delete system roles or roles with active memberships.
    """
    result = await db.execute(
        select(Role).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete system roles"
        )

    # Check for active memberships
    membership_count = await db.execute(
        select(func.count(TeamMembership.id)).where(
            and_(
                TeamMembership.role_id == role_id,
                TeamMembership.is_active == True
            )
        )
    )
    count = membership_count.scalar()

    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role with {count} active memberships"
        )

    await db.delete(role)
    await db.commit()


# =============================================================================
# Team Endpoints
# =============================================================================

@router.get("/teams", response_model=TeamListResponse)
async def list_teams(
    syndicate_id: Optional[int] = Query(None, description="Filter by syndicate"),
    team_type: Optional[TeamType] = Query(None, description="Filter by team type"),
    is_active: bool = Query(True, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List teams.

    Non-admin users can only see teams in their syndicate.
    """
    query = select(Team).options(selectinload(Team.memberships))

    conditions = [Team.is_active == is_active]

    # Non-admin users can only see their syndicate's teams
    if current_user.role != UserRole.ADMIN:
        if current_user.syndicate_id:
            conditions.append(Team.syndicate_id == current_user.syndicate_id)
        else:
            # User without syndicate can't see any teams
            return {"teams": [], "total": 0}
    elif syndicate_id:
        conditions.append(Team.syndicate_id == syndicate_id)

    if team_type:
        conditions.append(Team.team_type == team_type)

    query = query.where(and_(*conditions)).order_by(Team.name)

    # Count total
    count_result = await db.execute(
        select(func.count(Team.id)).where(and_(*conditions))
    )
    total = count_result.scalar()

    # Get paginated results
    result = await db.execute(query.offset(skip).limit(limit))
    teams = result.scalars().all()

    # Add member count
    teams_with_count = []
    for team in teams:
        team_dict = {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "team_type": team.team_type,
            "syndicate_id": team.syndicate_id,
            "team_code": team.team_code,
            "contact_email": team.contact_email,
            "classes_of_business": team.classes_of_business or [],
            "is_active": team.is_active,
            "created_at": team.created_at,
            "updated_at": team.updated_at,
            "member_count": len([m for m in team.memberships if m.is_active])
        }
        teams_with_count.append(team_dict)

    return {
        "teams": teams_with_count,
        "total": total
    }


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_data: TeamCreate,
    current_user: User = Depends(require_team_manage_permission),
    db: AsyncSession = Depends(get_db)
) -> Team:
    """
    Create a new team.

    Requires team:manage permission.
    Non-admin users can only create teams in their syndicate.
    """
    # Verify syndicate exists
    syndicate_result = await db.execute(
        select(Syndicate).where(Syndicate.id == team_data.syndicate_id)
    )
    syndicate = syndicate_result.scalar_one_or_none()

    if not syndicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Syndicate not found"
        )

    # Non-admins can only create teams in their syndicate
    if current_user.role != UserRole.ADMIN:
        if current_user.syndicate_id != team_data.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create teams for other syndicates"
            )

    # Check for duplicate name in syndicate
    existing = await db.execute(
        select(Team).where(
            and_(
                Team.syndicate_id == team_data.syndicate_id,
                Team.name == team_data.name
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team with name '{team_data.name}' already exists in this syndicate"
        )

    # Create team
    team = Team(
        name=team_data.name,
        description=team_data.description,
        syndicate_id=team_data.syndicate_id,
        team_type=team_data.team_type,
        team_code=team_data.team_code,
        contact_email=team_data.contact_email,
        classes_of_business=team_data.classes_of_business,
        is_active=team_data.is_active
    )

    db.add(team)
    await db.commit()
    await db.refresh(team)

    return team


@router.get("/teams/{team_id}", response_model=TeamDetailResponse)
async def get_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get detailed team information including members.
    """
    result = await db.execute(
        select(Team)
        .options(
            selectinload(Team.memberships)
            .selectinload(TeamMembership.user),
            selectinload(Team.memberships)
            .selectinload(TeamMembership.role)
        )
        .where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check access
    if current_user.role != UserRole.ADMIN:
        if current_user.syndicate_id != team.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    # Build members list
    members = []
    for m in team.memberships:
        if m.is_active:
            members.append({
                "user_id": m.user_id,
                "full_name": m.user.full_name if m.user else "",
                "email": m.user.email if m.user else "",
                "role_name": m.role.name if m.role else "",
                "is_team_lead": m.is_team_lead,
                "is_active": m.is_active
            })

    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "team_type": team.team_type,
        "syndicate_id": team.syndicate_id,
        "team_code": team.team_code,
        "contact_email": team.contact_email,
        "classes_of_business": team.classes_of_business or [],
        "is_active": team.is_active,
        "created_at": team.created_at,
        "updated_at": team.updated_at,
        "member_count": len(members),
        "members": members
    }


@router.put("/teams/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int,
    team_data: TeamUpdate,
    current_user: User = Depends(require_team_manage_permission),
    db: AsyncSession = Depends(get_db)
) -> Team:
    """
    Update a team's information.
    """
    result = await db.execute(
        select(Team).where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check access
    if current_user.role != UserRole.ADMIN:
        if current_user.syndicate_id != team.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    # Update fields
    if team_data.name is not None:
        # Check for duplicate name
        existing = await db.execute(
            select(Team).where(
                and_(
                    Team.syndicate_id == team.syndicate_id,
                    Team.name == team_data.name,
                    Team.id != team_id
                )
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Team with name '{team_data.name}' already exists"
            )
        team.name = team_data.name

    if team_data.description is not None:
        team.description = team_data.description
    if team_data.team_type is not None:
        team.team_type = team_data.team_type
    if team_data.team_code is not None:
        team.team_code = team_data.team_code
    if team_data.contact_email is not None:
        team.contact_email = team_data.contact_email
    if team_data.classes_of_business is not None:
        team.classes_of_business = team_data.classes_of_business
    if team_data.is_active is not None:
        team.is_active = team_data.is_active

    await db.commit()
    await db.refresh(team)

    return team


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: int,
    current_user: User = Depends(require_team_manage_permission),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Delete a team.

    This will also remove all team memberships.
    """
    result = await db.execute(
        select(Team).where(Team.id == team_id)
    )
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check access
    if current_user.role != UserRole.ADMIN:
        if current_user.syndicate_id != team.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    await db.delete(team)
    await db.commit()


# =============================================================================
# Team Membership Endpoints
# =============================================================================

@router.get("/teams/{team_id}/members", response_model=TeamMembershipListResponse)
async def list_team_members(
    team_id: int,
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List all members of a team.
    """
    # Verify team exists and user has access
    team_result = await db.execute(
        select(Team).where(Team.id == team_id)
    )
    team = team_result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    if current_user.role != UserRole.ADMIN:
        if current_user.syndicate_id != team.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    # Query memberships
    query = (
        select(TeamMembership)
        .options(
            selectinload(TeamMembership.user),
            selectinload(TeamMembership.role),
            selectinload(TeamMembership.team)
        )
        .where(TeamMembership.team_id == team_id)
    )

    if is_active is not None:
        query = query.where(TeamMembership.is_active == is_active)

    result = await db.execute(query)
    memberships = result.scalars().all()

    # Format response
    membership_list = []
    for m in memberships:
        membership_list.append({
            "id": m.id,
            "user_id": m.user_id,
            "team_id": m.team_id,
            "role_id": m.role_id,
            "is_team_lead": m.is_team_lead,
            "is_active": m.is_active,
            "start_date": m.start_date,
            "end_date": m.end_date,
            "notes": m.notes,
            "created_at": m.created_at,
            "updated_at": m.updated_at,
            "user_email": m.user.email if m.user else None,
            "user_full_name": m.user.full_name if m.user else None,
            "role_name": m.role.name if m.role else None,
            "team_name": m.team.name if m.team else None
        })

    return {
        "memberships": membership_list,
        "total": len(membership_list)
    }


@router.post("/teams/{team_id}/members", response_model=TeamMembershipResponse, status_code=status.HTTP_201_CREATED)
async def add_team_member(
    team_id: int,
    member_data: TeamMemberAdd,
    current_user: User = Depends(require_team_manage_permission),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Add a member to a team.

    Requires team:manage permission or being a team lead of this team.
    """
    # Verify team exists
    team_result = await db.execute(
        select(Team).where(Team.id == team_id)
    )
    team = team_result.scalar_one_or_none()

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    # Check access (team:manage or team lead)
    can_manage = False
    if current_user.role == UserRole.ADMIN:
        can_manage = True
    elif current_user.syndicate_id == team.syndicate_id:
        # Check if user is team lead
        lead_result = await db.execute(
            select(TeamMembership).where(
                and_(
                    TeamMembership.team_id == team_id,
                    TeamMembership.user_id == current_user.id,
                    TeamMembership.is_team_lead == True,
                    TeamMembership.is_active == True
                )
            )
        )
        if lead_result.scalar_one_or_none():
            can_manage = True
        else:
            # Check team:manage permission
            can_manage = await check_user_permission(current_user, "team:manage", db)

    if not can_manage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Must be team lead or have team:manage permission"
        )

    # Verify user exists
    user_result = await db.execute(
        select(User).where(User.id == member_data.user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    # Verify role exists
    role_result = await db.execute(
        select(Role).where(Role.id == member_data.role_id)
    )
    role = role_result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role not found"
        )

    # Check if user is already a member
    existing = await db.execute(
        select(TeamMembership).where(
            and_(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == member_data.user_id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this team"
        )

    # Create membership
    membership = TeamMembership(
        user_id=member_data.user_id,
        team_id=team_id,
        role_id=member_data.role_id,
        is_team_lead=member_data.is_team_lead,
        start_date=member_data.start_date or datetime.now(timezone.utc),
        end_date=member_data.end_date,
        notes=member_data.notes,
        added_by_user_id=current_user.id,
        is_active=True
    )

    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "team_id": membership.team_id,
        "role_id": membership.role_id,
        "is_team_lead": membership.is_team_lead,
        "is_active": membership.is_active,
        "start_date": membership.start_date,
        "end_date": membership.end_date,
        "notes": membership.notes,
        "created_at": membership.created_at,
        "updated_at": membership.updated_at,
        "user_email": user.email,
        "user_full_name": user.full_name,
        "role_name": role.name,
        "team_name": team.name
    }


@router.put("/teams/{team_id}/members/{user_id}", response_model=TeamMembershipResponse)
async def update_team_member(
    team_id: int,
    user_id: str,
    member_data: TeamMemberUpdate,
    current_user: User = Depends(require_team_manage_permission),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Update a team member's role or status.
    """
    # Get membership
    result = await db.execute(
        select(TeamMembership)
        .options(
            selectinload(TeamMembership.user),
            selectinload(TeamMembership.role),
            selectinload(TeamMembership.team)
        )
        .where(
            and_(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == user_id
            )
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team membership not found"
        )

    # Check access
    if current_user.role != UserRole.ADMIN:
        if current_user.syndicate_id != membership.team.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    # Update fields
    if member_data.role_id is not None:
        # Verify role exists
        role_result = await db.execute(
            select(Role).where(Role.id == member_data.role_id)
        )
        if not role_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role not found"
            )
        membership.role_id = member_data.role_id

    if member_data.is_team_lead is not None:
        membership.is_team_lead = member_data.is_team_lead
    if member_data.is_active is not None:
        membership.is_active = member_data.is_active
    if member_data.end_date is not None:
        membership.end_date = member_data.end_date
    if member_data.notes is not None:
        membership.notes = member_data.notes

    await db.commit()
    await db.refresh(membership)

    # Reload relationships
    result = await db.execute(
        select(TeamMembership)
        .options(
            selectinload(TeamMembership.user),
            selectinload(TeamMembership.role),
            selectinload(TeamMembership.team)
        )
        .where(TeamMembership.id == membership.id)
    )
    membership = result.scalar_one()

    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "team_id": membership.team_id,
        "role_id": membership.role_id,
        "is_team_lead": membership.is_team_lead,
        "is_active": membership.is_active,
        "start_date": membership.start_date,
        "end_date": membership.end_date,
        "notes": membership.notes,
        "created_at": membership.created_at,
        "updated_at": membership.updated_at,
        "user_email": membership.user.email if membership.user else None,
        "user_full_name": membership.user.full_name if membership.user else None,
        "role_name": membership.role.name if membership.role else None,
        "team_name": membership.team.name if membership.team else None
    }


@router.delete("/teams/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: int,
    user_id: str,
    current_user: User = Depends(require_team_manage_permission),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Remove a member from a team.

    This deactivates the membership rather than deleting it for audit purposes.
    """
    # Get membership
    result = await db.execute(
        select(TeamMembership)
        .options(selectinload(TeamMembership.team))
        .where(
            and_(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == user_id
            )
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team membership not found"
        )

    # Check access
    if current_user.role != UserRole.ADMIN:
        if current_user.syndicate_id != membership.team.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    # Soft delete (deactivate)
    membership.is_active = False
    membership.end_date = datetime.now(timezone.utc)

    await db.commit()


# =============================================================================
# RBAC Seeding Endpoint (Admin Only)
# =============================================================================

SEED_PERMISSIONS = [
    {"name": "assessment:read", "resource": "assessment", "action": "read", "description": "View assessments", "category": "underwriting"},
    {"name": "assessment:write", "resource": "assessment", "action": "write", "description": "Create and edit assessments", "category": "underwriting"},
    {"name": "assessment:approve", "resource": "assessment", "action": "approve", "description": "Approve assessments", "category": "underwriting"},
    {"name": "assessment:delete", "resource": "assessment", "action": "delete", "description": "Delete assessments", "category": "underwriting"},
    {"name": "placement:read", "resource": "placement", "action": "read", "description": "View placements", "category": "underwriting"},
    {"name": "placement:write", "resource": "placement", "action": "write", "description": "Create and edit placements", "category": "underwriting"},
    {"name": "placement:approve", "resource": "placement", "action": "approve", "description": "Approve placements", "category": "underwriting"},
    {"name": "placement:submit", "resource": "placement", "action": "submit", "description": "Submit placements to market", "category": "underwriting"},
    {"name": "exposure:read", "resource": "exposure", "action": "read", "description": "View exposure data", "category": "risk"},
    {"name": "exposure:write", "resource": "exposure", "action": "write", "description": "Edit exposure data", "category": "risk"},
    {"name": "exposure:manage", "resource": "exposure", "action": "manage", "description": "Manage exposure limits and alerts", "category": "risk"},
    {"name": "compliance:read", "resource": "compliance", "action": "read", "description": "View compliance reports", "category": "compliance"},
    {"name": "compliance:write", "resource": "compliance", "action": "write", "description": "Create compliance submissions", "category": "compliance"},
    {"name": "compliance:approve", "resource": "compliance", "action": "approve", "description": "Approve compliance submissions", "category": "compliance"},
    {"name": "pricing:read", "resource": "pricing", "action": "read", "description": "View pricing calculations", "category": "underwriting"},
    {"name": "pricing:write", "resource": "pricing", "action": "write", "description": "Run pricing calculations", "category": "underwriting"},
    {"name": "pricing:approve", "resource": "pricing", "action": "approve", "description": "Approve pricing decisions", "category": "underwriting"},
    {"name": "quote:read", "resource": "quote", "action": "read", "description": "View quotes", "category": "underwriting"},
    {"name": "quote:write", "resource": "quote", "action": "write", "description": "Create and edit quotes", "category": "underwriting"},
    {"name": "quote:approve", "resource": "quote", "action": "approve", "description": "Approve quotes", "category": "underwriting"},
    {"name": "document:read", "resource": "document", "action": "read", "description": "View documents", "category": "documents"},
    {"name": "document:write", "resource": "document", "action": "write", "description": "Upload and edit documents", "category": "documents"},
    {"name": "document:delete", "resource": "document", "action": "delete", "description": "Delete documents", "category": "documents"},
    {"name": "team:read", "resource": "team", "action": "read", "description": "View team information", "category": "administration"},
    {"name": "team:manage", "resource": "team", "action": "manage", "description": "Manage team members and roles", "category": "administration"},
    {"name": "user:read", "resource": "user", "action": "read", "description": "View user profiles", "category": "administration"},
    {"name": "user:manage", "resource": "user", "action": "manage", "description": "Manage user accounts", "category": "administration"},
    {"name": "claims:read", "resource": "claims", "action": "read", "description": "View claims", "category": "claims"},
    {"name": "claims:write", "resource": "claims", "action": "write", "description": "Create and edit claims", "category": "claims"},
    {"name": "claims:approve", "resource": "claims", "action": "approve", "description": "Approve claims", "category": "claims"},
    {"name": "report:read", "resource": "report", "action": "read", "description": "View reports", "category": "reporting"},
    {"name": "report:generate", "resource": "report", "action": "write", "description": "Generate reports", "category": "reporting"},
    {"name": "integration:read", "resource": "integration", "action": "read", "description": "View integrations", "category": "technical"},
    {"name": "integration:manage", "resource": "integration", "action": "manage", "description": "Manage integrations", "category": "technical"},
    {"name": "audit:read", "resource": "audit", "action": "read", "description": "View audit logs", "category": "administration"},
]

SEED_ROLES = [
    {"name": "Admin", "description": "Full system administrator with all permissions", "hierarchy_level": 40, "permissions": [p["name"] for p in SEED_PERMISSIONS]},
    {"name": "Lead Underwriter", "description": "Senior underwriter with approval authority", "hierarchy_level": 30, "permissions": ["assessment:read", "assessment:write", "assessment:approve", "assessment:delete", "placement:read", "placement:write", "placement:approve", "placement:submit", "exposure:read", "exposure:write", "exposure:manage", "pricing:read", "pricing:write", "pricing:approve", "quote:read", "quote:write", "quote:approve", "document:read", "document:write", "team:read", "report:read", "report:generate"]},
    {"name": "Senior Underwriter", "description": "Experienced underwriter with write access", "hierarchy_level": 20, "permissions": ["assessment:read", "assessment:write", "placement:read", "placement:write", "exposure:read", "exposure:write", "pricing:read", "pricing:write", "quote:read", "quote:write", "document:read", "document:write", "team:read", "report:read"]},
    {"name": "Junior Underwriter", "description": "Entry-level underwriter with limited write access", "hierarchy_level": 10, "permissions": ["assessment:read", "assessment:write", "placement:read", "exposure:read", "pricing:read", "quote:read", "document:read", "document:write", "team:read", "report:read"]},
    {"name": "Compliance Officer", "description": "Compliance specialist with compliance and audit access", "hierarchy_level": 25, "permissions": ["assessment:read", "placement:read", "exposure:read", "compliance:read", "compliance:write", "compliance:approve", "document:read", "team:read", "report:read", "report:generate", "audit:read"]},
    {"name": "Claims Handler", "description": "Claims processing specialist", "hierarchy_level": 15, "permissions": ["assessment:read", "placement:read", "claims:read", "claims:write", "document:read", "document:write", "team:read", "report:read"]},
    {"name": "Claims Manager", "description": "Claims manager with approval authority", "hierarchy_level": 25, "permissions": ["assessment:read", "placement:read", "claims:read", "claims:write", "claims:approve", "document:read", "document:write", "team:read", "team:manage", "report:read", "report:generate"]},
    {"name": "Viewer", "description": "Read-only access to the system", "hierarchy_level": 0, "permissions": ["assessment:read", "placement:read", "exposure:read", "compliance:read", "pricing:read", "quote:read", "document:read", "team:read", "claims:read", "report:read"]},
]


@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_rbac_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Seed RBAC permissions and roles (Admin only).
    Creates 34 permissions and 8 system roles.
    """
    # Check admin permission
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    created_permissions = 0
    created_roles = 0
    permission_map = {}

    # Seed permissions
    for perm_data in SEED_PERMISSIONS:
        result = await db.execute(
            select(Permission).where(Permission.name == perm_data["name"])
        )
        existing = result.scalar_one_or_none()
        if not existing:
            perm = Permission(
                name=perm_data["name"],
                resource=perm_data["resource"],
                action=perm_data["action"],
                description=perm_data["description"],
                category=perm_data["category"],
                is_active=True,
            )
            db.add(perm)
            await db.flush()
            permission_map[perm_data["name"]] = perm
            created_permissions += 1
        else:
            permission_map[perm_data["name"]] = existing

    # Seed roles
    for role_data in SEED_ROLES:
        result = await db.execute(
            select(Role).where(Role.name == role_data["name"])
        )
        existing = result.scalar_one_or_none()
        if not existing:
            role = Role(
                name=role_data["name"],
                description=role_data["description"],
                is_system_role=True,
                hierarchy_level=role_data["hierarchy_level"],
                is_active=True,
            )
            for perm_name in role_data["permissions"]:
                if perm_name in permission_map:
                    role.permissions.append(permission_map[perm_name])
            db.add(role)
            created_roles += 1

    await db.commit()

    return {
        "status": "success",
        "created_permissions": created_permissions,
        "created_roles": created_roles,
        "total_permissions": len(SEED_PERMISSIONS),
        "total_roles": len(SEED_ROLES)
    }
