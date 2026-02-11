"""
InstantRisk V3 - RBAC Pydantic Schemas

This module defines Pydantic schemas for RBAC-related CRUD operations:
- Permission schemas
- Role schemas
- Team schemas
- Team membership schemas
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.models.rbac import TeamType


# =============================================================================
# Permission Schemas
# =============================================================================

class PermissionBase(BaseModel):
    """Base schema for permissions."""
    resource: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None


class PermissionCreate(PermissionBase):
    """Schema for creating a new permission."""
    name: Optional[str] = None  # Auto-generated if not provided
    category: Optional[str] = None
    is_active: bool = True


class PermissionResponse(PermissionBase):
    """Schema for permission response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: Optional[str] = None
    is_active: bool
    created_at: datetime


class PermissionBrief(BaseModel):
    """Brief permission info for lists."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None


# =============================================================================
# Role Schemas
# =============================================================================

class RoleBase(BaseModel):
    """Base schema for roles."""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None


class RoleCreate(RoleBase):
    """Schema for creating a new role."""
    permission_ids: List[int] = Field(default_factory=list)
    permission_names: List[str] = Field(default_factory=list)
    # Can specify either IDs or names

    syndicate_id: Optional[int] = None  # Null = global role
    hierarchy_level: int = Field(default=0, ge=0, le=100)
    is_active: bool = True


class RoleUpdate(BaseModel):
    """Schema for updating an existing role."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None
    permission_names: Optional[List[str]] = None
    hierarchy_level: Optional[int] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class RoleResponse(RoleBase):
    """Schema for role response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_system_role: bool
    is_active: bool
    syndicate_id: Optional[int] = None
    hierarchy_level: int
    permissions: List[PermissionBrief] = []
    created_at: datetime
    updated_at: datetime


class RoleBrief(BaseModel):
    """Brief role info for lists."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    hierarchy_level: int


class RoleListResponse(BaseModel):
    """Response for list of roles."""
    roles: List[RoleResponse]
    total: int


# =============================================================================
# Team Schemas
# =============================================================================

class TeamBase(BaseModel):
    """Base schema for teams."""
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    team_type: TeamType = TeamType.UNDERWRITING


class TeamCreate(TeamBase):
    """Schema for creating a new team."""
    syndicate_id: int
    team_code: Optional[str] = Field(None, max_length=50)
    contact_email: Optional[str] = None
    classes_of_business: List[str] = Field(default_factory=list)
    is_active: bool = True


class TeamUpdate(BaseModel):
    """Schema for updating an existing team."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    team_type: Optional[TeamType] = None
    team_code: Optional[str] = Field(None, max_length=50)
    contact_email: Optional[str] = None
    classes_of_business: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TeamMemberBrief(BaseModel):
    """Brief team member info."""
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    full_name: str
    email: str
    role_name: str
    is_team_lead: bool
    is_active: bool


class TeamResponse(TeamBase):
    """Schema for team response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    syndicate_id: int
    team_code: Optional[str] = None
    contact_email: Optional[str] = None
    classes_of_business: List[str] = []
    is_active: bool
    created_at: datetime
    updated_at: datetime
    member_count: int = 0


class TeamDetailResponse(TeamResponse):
    """Detailed team response including members."""
    members: List[TeamMemberBrief] = []


class TeamListResponse(BaseModel):
    """Response for list of teams."""
    teams: List[TeamResponse]
    total: int


# =============================================================================
# Team Membership Schemas
# =============================================================================

class TeamMemberAdd(BaseModel):
    """Schema for adding a member to a team."""
    user_id: UUID
    role_id: int
    is_team_lead: bool = False
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("end_date")
    @classmethod
    def end_date_after_start(cls, v, info):
        if v and info.data.get("start_date") and v <= info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class TeamMemberUpdate(BaseModel):
    """Schema for updating a team membership."""
    role_id: Optional[int] = None
    is_team_lead: Optional[bool] = None
    is_active: Optional[bool] = None
    end_date: Optional[datetime] = None
    notes: Optional[str] = None


class TeamMembershipResponse(BaseModel):
    """Schema for team membership response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID
    team_id: int
    role_id: int
    is_team_lead: bool
    is_active: bool
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Nested info
    user_email: Optional[str] = None
    user_full_name: Optional[str] = None
    role_name: Optional[str] = None
    team_name: Optional[str] = None


class TeamMembershipListResponse(BaseModel):
    """Response for list of team memberships."""
    memberships: List[TeamMembershipResponse]
    total: int


# =============================================================================
# User Permissions Schemas
# =============================================================================

class UserPermissionsResponse(BaseModel):
    """Response containing all effective permissions for a user."""
    user_id: UUID
    user_email: str
    permissions: List[str]  # List of permission names
    teams: List[dict]  # List of team info with roles
    is_syndicate_admin: bool = False


class PermissionCheckRequest(BaseModel):
    """Request to check if user has permission."""
    permission_name: str  # e.g., "assessment:write"


class PermissionCheckResponse(BaseModel):
    """Response for permission check."""
    has_permission: bool
    permission_name: str
    granted_via: Optional[str] = None  # e.g., "Role: Lead Underwriter"


class BulkPermissionCheckRequest(BaseModel):
    """Request to check multiple permissions."""
    permissions: List[str]


class BulkPermissionCheckResponse(BaseModel):
    """Response for bulk permission check."""
    results: dict  # {permission_name: bool}
    all_granted: bool


# =============================================================================
# RBAC Audit Schemas
# =============================================================================

class RBACChangeLog(BaseModel):
    """Schema for RBAC change audit log."""
    id: int
    timestamp: datetime
    action: str  # e.g., "add_member", "remove_member", "change_role"
    entity_type: str  # "team", "role", "permission"
    entity_id: int
    actor_user_id: UUID
    actor_email: str
    details: dict
