"""
InstantRisk V3 - RBAC (Role-Based Access Control) Models

This module defines models for teams and granular permission-based access control:
- Permission: Granular permissions for resources and actions
- Role: Named roles with sets of permissions
- Team: Teams within syndicates for organizational grouping
- TeamMembership: Association between users, teams, and roles
"""

from datetime import datetime, timezone
from typing import List, Optional
import enum

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    ForeignKey, Table, Enum, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PgUUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# =============================================================================
# Enums
# =============================================================================

class TeamType(str, enum.Enum):
    """Types of teams within a syndicate."""
    UNDERWRITING = "underwriting"
    CLAIMS = "claims"
    COMPLIANCE = "compliance"
    OPERATIONS = "operations"
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    CUSTOM = "custom"


class PermissionAction(str, enum.Enum):
    """Standard permission actions."""
    READ = "read"
    WRITE = "write"
    APPROVE = "approve"
    DELETE = "delete"
    MANAGE = "manage"
    SUBMIT = "submit"


class PermissionResource(str, enum.Enum):
    """Resources that can be controlled via permissions."""
    ASSESSMENT = "assessment"
    PLACEMENT = "placement"
    EXPOSURE = "exposure"
    COMPLIANCE = "compliance"
    PRICING = "pricing"
    QUOTE = "quote"
    DOCUMENT = "document"
    TEAM = "team"
    USER = "user"
    CLAIMS = "claims"
    REPORT = "report"
    INTEGRATION = "integration"
    AUDIT = "audit"


# =============================================================================
# Association Table for Role-Permission Many-to-Many
# =============================================================================

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


# =============================================================================
# Permission Model
# =============================================================================

class Permission(Base):
    """
    Granular permission representing an action on a resource.

    Examples:
    - assessment:read - Can view assessments
    - assessment:write - Can create/edit assessments
    - assessment:approve - Can approve assessments
    - placement:write - Can create/edit placements
    - team:manage - Can manage team members
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)

    # Permission identification
    name = Column(String(100), unique=True, nullable=False, index=True)
    # Format: resource:action (e.g., "assessment:read")

    # Human-readable description
    description = Column(Text, nullable=True)

    # Structured permission components
    resource = Column(String(50), nullable=False, index=True)
    # e.g., "assessment", "placement", "exposure"

    action = Column(String(50), nullable=False)
    # e.g., "read", "write", "approve", "delete"

    # Status
    is_active = Column(Boolean, default=True)

    # Metadata
    category = Column(String(50), nullable=True)
    # e.g., "underwriting", "compliance", "administration"

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    roles = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions"
    )

    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
        Index("idx_permission_resource", "resource"),
    )

    def __repr__(self) -> str:
        return f"<Permission({self.name})>"

    @property
    def full_name(self) -> str:
        """Returns the permission in resource:action format."""
        return f"{self.resource}:{self.action}"


# =============================================================================
# Role Model
# =============================================================================

class Role(Base):
    """
    Named role with a collection of permissions.

    Examples:
    - Lead Underwriter: Full underwriting permissions
    - Junior Underwriter: Read-only access
    - Compliance Officer: Compliance-specific permissions
    - Team Admin: Team management permissions
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)

    # Role identification
    name = Column(String(100), unique=True, nullable=False, index=True)

    # Human-readable description
    description = Column(Text, nullable=True)

    # Role metadata
    is_system_role = Column(Boolean, default=False)
    # System roles cannot be deleted or renamed

    is_active = Column(Boolean, default=True)

    # Syndicate scope (null = global role available to all)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=True)
    # If set, role is only available within that syndicate

    # Role hierarchy level (higher = more permissions typically)
    hierarchy_level = Column(Integer, default=0)
    # 0 = basic, 10 = senior, 20 = lead, 30 = manager, 40 = admin

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles"
    )

    syndicate = relationship("Syndicate", backref="custom_roles")
    team_memberships = relationship("TeamMembership", back_populates="role")

    __table_args__ = (
        Index("idx_role_syndicate", "syndicate_id"),
    )

    def __repr__(self) -> str:
        return f"<Role({self.name}, permissions={len(self.permissions or [])})>"

    def has_permission(self, permission_name: str) -> bool:
        """Check if this role has a specific permission."""
        return any(p.name == permission_name for p in (self.permissions or []))

    def has_resource_permission(self, resource: str, action: str) -> bool:
        """Check if this role has a specific resource:action permission."""
        return any(
            p.resource == resource and p.action == action
            for p in (self.permissions or [])
        )


# =============================================================================
# Team Model
# =============================================================================

class Team(Base):
    """
    Team within a syndicate for organizational grouping.

    Teams allow syndicates to organize users into functional groups
    like "Marine Underwriting", "Property Claims", etc.
    """
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)

    # Team identification
    name = Column(String(255), nullable=False)

    # Human-readable description
    description = Column(Text, nullable=True)

    # Syndicate association (required)
    syndicate_id = Column(Integer, ForeignKey("syndicates.id"), nullable=False, index=True)

    # Team classification
    team_type = Column(
        Enum(TeamType, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        default=TeamType.UNDERWRITING,
        nullable=False
    )

    # Optional: Team code for reference
    team_code = Column(String(50), nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Contact information
    contact_email = Column(String(255), nullable=True)

    # Class of business focus (optional)
    classes_of_business = Column(ARRAY(String), default=list)
    # e.g., ["marine", "property", "casualty"]

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    syndicate = relationship("Syndicate", backref="teams")
    memberships = relationship(
        "TeamMembership",
        back_populates="team",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("syndicate_id", "name", name="uq_team_syndicate_name"),
        Index("idx_team_syndicate", "syndicate_id"),
        Index("idx_team_type", "team_type"),
    )

    def __repr__(self) -> str:
        return f"<Team({self.name}, syndicate_id={self.syndicate_id})>"

    @property
    def member_count(self) -> int:
        """Returns the number of active members in the team."""
        return len([m for m in (self.memberships or []) if m.is_active])

    @property
    def team_leads(self) -> List["TeamMembership"]:
        """Returns list of team lead memberships."""
        return [m for m in (self.memberships or []) if m.is_team_lead and m.is_active]


# =============================================================================
# Team Membership Model
# =============================================================================

class TeamMembership(Base):
    """
    Association between a user, team, and their role within that team.

    A user can be a member of multiple teams with different roles.
    """
    __tablename__ = "team_memberships"

    id = Column(Integer, primary_key=True, index=True)

    # User association
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Team association
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)

    # Role within the team
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)

    # Team lead status
    is_team_lead = Column(Boolean, default=False)
    # Team leads can manage team membership

    # Membership status
    is_active = Column(Boolean, default=True)

    # Optional: Start and end dates for temporary assignments
    start_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    end_date = Column(DateTime(timezone=True), nullable=True)

    # Notes (e.g., "Temporary assignment during leave")
    notes = Column(Text, nullable=True)

    # Added by (for audit)
    added_by_user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="team_memberships")
    team = relationship("Team", back_populates="memberships")
    role = relationship("Role", back_populates="team_memberships")
    added_by = relationship("User", foreign_keys=[added_by_user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "team_id", name="uq_user_team"),
        Index("idx_membership_user", "user_id"),
        Index("idx_membership_team", "team_id"),
        Index("idx_membership_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<TeamMembership(user_id={self.user_id}, team_id={self.team_id}, role_id={self.role_id})>"

    @property
    def is_expired(self) -> bool:
        """Check if membership has expired (if end_date is set)."""
        if self.end_date is None:
            return False
        return datetime.now(timezone.utc) > self.end_date


# =============================================================================
# User Permission Cache (for performance)
# =============================================================================

class UserPermissionCache(Base):
    """
    Cached effective permissions for a user.

    This denormalized table improves permission check performance
    by pre-computing all permissions a user has across all teams.
    """
    __tablename__ = "user_permission_cache"

    id = Column(Integer, primary_key=True, index=True)

    # User
    user_id = Column(PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Cached permission
    permission_name = Column(String(100), nullable=False, index=True)

    # Source (for debugging)
    source_team_id = Column(Integer, nullable=True)
    source_role_id = Column(Integer, nullable=True)

    # Cache metadata
    cached_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", backref="permission_cache")

    __table_args__ = (
        UniqueConstraint("user_id", "permission_name", name="uq_user_permission_cache"),
        Index("idx_user_perm_cache", "user_id", "permission_name"),
    )

    def __repr__(self) -> str:
        return f"<UserPermissionCache(user_id={self.user_id}, permission={self.permission_name})>"
