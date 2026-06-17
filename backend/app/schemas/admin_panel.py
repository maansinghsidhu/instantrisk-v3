"""
InstantRisk V3 - Admin Panel Schemas

Pydantic schemas for the admin panel API: user list/detail, usage,
billing summary, audit log, and admin actions.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict

from app.models.subscription import SubscriptionTier, SubscriptionStatus
from app.models.user import UserRole, ApprovalStatus


# =============================================================================
# User list / detail
# =============================================================================

class AdminUserSummary(BaseModel):
    """Compact user row for the admin list view."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str
    approval_status: str
    is_active: bool
    is_verified: bool
    two_fa_enabled: bool
    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None


class AdminUserDetail(AdminUserSummary):
    """Full user row for the detail view."""
    rejection_reason: Optional[str] = None
    approved_by: Optional[str] = None
    syndicate_id: Optional[int] = None
    commission_rate: Optional[float] = None
    preferred_language: Optional[str] = None
    subscription_started_at: Optional[datetime] = None
    subscription_expires_at: Optional[datetime] = None


class AdminUserListResponse(BaseModel):
    users: List[AdminUserSummary]
    total: int
    limit: int
    offset: int


# =============================================================================
# Usage
# =============================================================================

class AdminUserUsage(BaseModel):
    """Per-user usage counters (current month) and lifetime."""
    user_id: str
    email: str
    subscription_tier: Optional[str] = None
    monthly_assessments_used: int
    monthly_documents_generated: int
    monthly_chat_messages_used: int
    monthly_assessments_limit: int
    monthly_documents_limit: int
    monthly_chat_messages_limit: int
    usage_reset_at: Optional[datetime] = None
    lifetime_assessments: int
    lifetime_documents: int
    lifetime_chat_messages: int


# =============================================================================
# Billing
# =============================================================================

TIER_PRICE_USD = {
    SubscriptionTier.TRIAL: 0,
    SubscriptionTier.BASIC: 99,
    SubscriptionTier.PREMIUM: 499,
}


class AdminBillingSummary(BaseModel):
    """Platform-wide billing rollup."""
    total_users: int
    users_by_tier: Dict[str, int]
    users_by_status: Dict[str, int]
    monthly_recurring_revenue_usd: int
    annual_recurring_revenue_usd: int
    trialing_users: int
    pending_payment_failures: int
    generated_at: datetime = Field(default_factory=lambda: datetime.utcnow())


# =============================================================================
# Audit log
# =============================================================================

class AdminAuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    admin_id: str
    admin_email: Optional[str] = None
    target_user_id: Optional[str] = None
    target_user_email: Optional[str] = None
    action: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


class AdminAuditLogResponse(BaseModel):
    entries: List[AdminAuditLogEntry]
    total: int
    limit: int
    offset: int


# =============================================================================
# Admin actions
# =============================================================================

class AdminApproveRequest(BaseModel):
    subscription_tier: str = Field(
        "basic", description="trial | basic | premium"
    )
    notes: Optional[str] = Field(None, max_length=1000)


class AdminRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class AdminTierChangeRequest(BaseModel):
    subscription_tier: str = Field(..., description="trial | basic | premium")
    reason: Optional[str] = Field(None, max_length=1000)


class AdminDeactivateRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000)


class AdminActionResponse(BaseModel):
    success: bool
    message: str
    user_id: str
    action: str
    new_state: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Admin stats
# =============================================================================

class AdminStats(BaseModel):
    """High-level admin dashboard counts."""
    total_users: int
    active_users: int
    pending_approvals: int
    rejected_users: int
    users_with_2fa: int
    users_by_role: Dict[str, int]
    users_by_tier: Dict[str, int]
    generated_at: datetime = Field(default_factory=lambda: datetime.utcnow)
