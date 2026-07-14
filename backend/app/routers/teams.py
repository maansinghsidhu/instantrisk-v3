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
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_tenant_db_for_user
from app.core.security import get_current_user
from app.core.permissions import (
    clear_user_permission_cache,
    clear_permission_cache_for_role,
)
from app.services.audit_service import log_audit
from app.models.audit_log import AuditAction, AuditOutcome
from app.models.user import User, UserRole
from app.models.syndicate import Syndicate
from app.models.rbac import (
    Permission,
    Role,
    Team,
    TeamMembership,
    TeamType,
    UserPermissionCache,
    role_permissions,
)
from app.schemas.rbac import (
    # Permission schemas
    PermissionResponse,
    # Role schemas
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
    # Team schemas
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    TeamDetailResponse,
    TeamMembershipListResponse,
    TeamMembershipResponse,
    UserPermissionsResponse,
    TeamTypeEnum,
    BulkPermissionCheckResponse,
    PermissionCheckResponse,
)
from app.core.permissions import (
    check_user_permission,
    require_permission,
    require_team_manage_permission,
    get_user_permissions_async,
)

# Permission schemas
PermissionBrief = None  # type: ignore
router = APIRouter()
