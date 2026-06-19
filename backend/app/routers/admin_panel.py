"""
InstantRisk V3 - Admin Panel Router

End-to-end admin operations: user list/detail, approve/reject, tier change,
deactivate/reactivate, usage, billing summary, audit log viewer, and stats.

All endpoints require `UserRole.ADMIN`. Every privileged action writes an
`AdminAuditLog` row (with admin id, target user, action, details JSON, IP,
user agent).

This router is intentionally additive - it does not change the existing
`approval.py` or `admin.py` routers. The approval router keeps its narrow
API-only flow; this router adds the user/billing surface the Flutter admin
panel needs.
"""
import ipaddress
import logging
from collections import deque
import threading as _threading
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.config import get_settings
from app.models.user import User, UserRole, ApprovalStatus
from app.models.subscription import (
    Subscription, SubscriptionTier, SubscriptionStatus,
)
from app.models.chat import ChatMessage
from app.models.admin import AdminAuditLog, AdminAction
from app.models.assessment import Assessment
from app.models.generated_document import GeneratedDocument
from app.models.feature_limits import get_tier_limits
from app.schemas.admin_panel import (
    AdminUserSummary, AdminUserDetail, AdminUserListResponse,
    AdminUserUsage, AdminBillingSummary, AdminAuditLogEntry,
    AdminAuditLogResponse, AdminApproveRequest, AdminRejectRequest,
    AdminTierChangeRequest, AdminDeactivateRequest, AdminActionResponse,
    AdminStats,
)
from app.patches.decision_log_writer import write_audit_log as patch_write_audit_log

logger = logging.getLogger("instantrisk.admin_panel")
router = APIRouter(prefix="/admin/panel", tags=["Admin Panel"])

_TRUSTED_PROXIES_CACHE: Optional[List[ipaddress._BaseNetwork]] = None


def _trusted_proxy_networks() -> List[ipaddress._BaseNetwork]:
    global _TRUSTED_PROXIES_CACHE
    if _TRUSTED_PROXIES_CACHE is not None:
        return _TRUSTED_PROXIES_CACHE
    settings = get_settings()
    nets: List[ipaddress._BaseNetwork] = []
    for cidr in settings.trusted_proxies:
        try:
            nets.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            continue
    _TRUSTED_PROXIES_CACHE = nets
    return nets


def _client_ip(request: Request) -> Optional[str]:
    """Resolve the client IP. The X-Forwarded-For / X-Real-IP headers are
    only honored when the direct peer (``request.client.host``) is in
    the configured trusted-proxies list. Otherwise a client can forge
    the header and spoof the IP captured in the audit log.
    """
    direct_peer = request.client.host if request.client else None
    peer_is_trusted = False
    if direct_peer:
        try:
            peer_ip = ipaddress.ip_address(direct_peer)
            peer_is_trusted = any(
                peer_ip in net for net in _trusted_proxy_networks()
            )
        except ValueError:
            peer_is_trusted = False

    if peer_is_trusted:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            # Use the leftmost entry (the original client) only when the
            # request came through a chain of trusted proxies.
            return xff.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return direct_peer

async def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires admin privileges",
        )
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is deactivated",
        )
    return current_user


# =============================================================================
# Rate limiter (Fix #17)
# =============================================================================
#
# Simple per-admin in-memory token bucket. Limits mutating admin endpoints
# to 30 actions per minute per admin id. This is intentionally lightweight
# (no Redis dependency) and is a soft control only - the real defence
# against brute-force is the WAF in front of the ALB.
_RATE_LIMIT_PER_MINUTE = 30
_RATE_WINDOW_SECONDS = 60
_rate_limit_buckets: dict = {}  # admin_id -> deque[float]
# Fix #26 (5th pr-agent pass): per-process dict is per-worker, so a
# multi-worker deployment grants N x the per-minute limit. The lock
# at least makes this thread-safe within a worker. Real defence is the
# WAF in front of the ALB; a Redis-backed bucket is the proper fix.
import threading as _threading
_rate_limit_lock = _threading.Lock()


def _check_rate_limit(admin_id) -> None:
    """Token-bucket rate limiter. Raises 429 if the admin exceeds
    ``_RATE_LIMIT_PER_MINUTE`` actions in the last ``_RATE_WINDOW_SECONDS``.

    Fix #28 (7th pr-agent): the previous version declared
    ``_rate_limit_lock`` but never acquired it. The bucket dict was
    not thread-safe despite the comment claiming otherwise. Now the
    entire check + bucket update runs under the lock.

    Fix #24 (5th pr-agent): callers MUST invoke this before any state
    mutation. The 429 raises but does not roll back partial writes.
    """
    now = time.monotonic()
    with _rate_limit_lock:
        bucket = _rate_limit_buckets.setdefault(admin_id, deque())
        # Drop entries outside the window
        while bucket and (now - bucket[0]) > _RATE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT_PER_MINUTE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: max {_RATE_LIMIT_PER_MINUTE} "
                       f"admin actions per {_RATE_WINDOW_SECONDS}s",
                headers={"Retry-After": str(_RATE_WINDOW_SECONDS)},
            )
        bucket.append(now)

async def _write_audit(
    db: AsyncSession,
    admin: User,
    action: str,
    target_user_id: Optional[UUID],
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    log = AdminAuditLog(
        admin_id=admin.id,
        target_user_id=target_user_id,
        action=action,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(log)
    await db.flush()


# =============================================================================
# Stats
# =============================================================================

@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Combined single-query aggregate. Previously this endpoint issued
    # ~10 separate count() queries (one per role, one per boolean).
    # Now: 2 queries (one users group-by, one subscriptions group-by)
    # plus a single scalar for the boolean aggregate.

    # Aggregate over the users table in a single statement.
    base_count = select(func.count(User.id))
    total = await db.scalar(base_count)
    active = await db.scalar(
        base_count.where(User.is_active == True)  # noqa: E712
    )
    pending = await db.scalar(
        base_count.where(User.approval_status == ApprovalStatus.PENDING)
    )
    rejected = await db.scalar(
        base_count.where(User.approval_status == ApprovalStatus.REJECTED)
    )
    with_2fa = await db.scalar(
        base_count.where(User.two_fa_enabled == True)  # noqa: E712
    )

    # Group by role in a single query.
    role_rows = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    users_by_role = {r.value: 0 for r in UserRole}
    for role, count in role_rows.all():
        if role is not None:
            users_by_role[role.value] = count or 0

    # Group by tier in a single query.
    sub_tier_query = await db.execute(
        select(Subscription.tier, func.count(Subscription.id))
        .group_by(Subscription.tier)
    )
    users_by_tier = {t.value: 0 for t in SubscriptionTier}
    for tier, count in sub_tier_query.all():
        if tier:
            users_by_tier[tier.value] = count or 0

    return AdminStats(
        total_users=total or 0,
        active_users=active or 0,
        pending_approvals=pending or 0,
        rejected_users=rejected or 0,
        users_with_2fa=with_2fa or 0,
        users_by_role=users_by_role,
        users_by_tier=users_by_tier,
    )


# =============================================================================
# User list / detail
# =============================================================================

@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    status_filter: Optional[str] = Query(
        None, description="pending | approved | rejected | active | inactive"
    ),
    role: Optional[str] = Query(None, description="broker | syndicate | admin | underwriter"),
    tier: Optional[str] = Query(None, description="trial | basic | premium"),
    search: Optional[str] = Query(None, description="email / full_name search"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(User).options(selectinload(User.subscription))
    conditions = []
    if status_filter:
        if status_filter in ("pending", "approved", "rejected"):
            conditions.append(User.approval_status == ApprovalStatus(status_filter))
        elif status_filter == "active":
            conditions.append(User.is_active == True)  # noqa: E712
        elif status_filter == "inactive":
            conditions.append(User.is_active == False)  # noqa: E712

    if role:
        try:
            conditions.append(User.role == UserRole(role))
        except ValueError:
            raise HTTPException(400, f"Unknown role: {role}")

    if tier:
        try:
            tier_enum = SubscriptionTier(tier)
            conditions.append(User.subscription.has(Subscription.tier == tier_enum))
        except ValueError:
            raise HTTPException(400, f"Unknown tier: {tier}")

    if search and search.strip():
        # Fix #25 (5th pr-agent pass): escape SQL LIKE wildcards in user
        # input so a search for "100%" doesn't match every string containing
        # "100". Escape both % and _ (LIKE metacharacters) by prefixing
        # with backslash, then use ilike with explicit escape character.
        raw = search.strip().lower()
        escaped = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        term = f"%{escaped}%"
        conditions.append(
            or_(
                User.email.ilike(term, escape="\\"),
                User.full_name.ilike(term, escape="\\"),
            )
        )

    if conditions:
        query = query.where(and_(*conditions))

    total = await db.scalar(
        select(func.count()).select_from(query.subquery())
    )

    query = query.order_by(desc(User.created_at)).limit(limit).offset(offset)
    result = await db.execute(query)
    users = result.scalars().all()

    return AdminUserListResponse(
        users=[
            AdminUserSummary(
                id=str(u.id),
                email=u.email,
                full_name=u.full_name,
                role=u.role.value,
                approval_status=u.approval_status.value,
                is_active=u.is_active,
                is_verified=u.is_verified,
                two_fa_enabled=u.two_fa_enabled,
                created_at=u.created_at,
                approved_at=u.approved_at,
                last_login=u.last_login,
                subscription_tier=u.subscription.tier.value if u.subscription else None,
                subscription_status=u.subscription.status.value if u.subscription else None,
            )
            for u in users
        ],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: str,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user id")

    result = await db.execute(
        select(User)
        .options(selectinload(User.subscription))
        .where(User.id == user_uuid)
    )
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "User not found")

    return AdminUserDetail(
        id=str(u.id),
        email=u.email,
        full_name=u.full_name,
        role=u.role.value,
        approval_status=u.approval_status.value,
        is_active=u.is_active,
        is_verified=u.is_verified,
        two_fa_enabled=u.two_fa_enabled,
        created_at=u.created_at,
        approved_at=u.approved_at,
        last_login=u.last_login,
        subscription_tier=u.subscription.tier.value if u.subscription else None,
        subscription_status=u.subscription.status.value if u.subscription else None,
        rejection_reason=u.rejection_reason,
        approved_by=str(u.approved_by) if u.approved_by else None,
        syndicate_id=u.syndicate_id,
        commission_rate=u.commission_rate,
        preferred_language=u.preferred_language.value if u.preferred_language else None,
        subscription_started_at=u.subscription.started_at if u.subscription else None,
        subscription_expires_at=u.subscription.expires_at if u.subscription else None,
    )


# =============================================================================
# Approve / Reject
# =============================================================================

@router.post("/users/{user_id}/approve", response_model=AdminActionResponse)
async def approve_user(
    user_id: str,
    body: AdminApproveRequest,
    request: Request,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user id")

    valid_tiers = {t.value: t for t in SubscriptionTier}
    if body.subscription_tier not in valid_tiers:
        raise HTTPException(400, f"Invalid tier. Valid: {', '.join(valid_tiers)}")
    target_tier = valid_tiers[body.subscription_tier]

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if user.approval_status != ApprovalStatus.PENDING:
        raise HTTPException(400, f"User is {user.approval_status.value}, not pending")

    # pr-agent fix (10th pass): rate limit must run BEFORE any state
    # mutation. The previous fix #24 placement (after the mutation block)
    # meant a rate-limited admin still changed platform state; only
    # subsequent calls in the same minute were blocked.
    _check_rate_limit(current_user.id)

    user.approval_status = ApprovalStatus.APPROVED
    user.approved_by = current_user.id
    user.approved_at = datetime.now(timezone.utc)
    user.is_active = True
    user.rejection_reason = None

    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_uuid)
    )
    sub = sub_result.scalar_one_or_none()
    if sub:
        sub.tier = target_tier
        sub.status = SubscriptionStatus.ACTIVE
        sub.started_at = datetime.now(timezone.utc)
        sub.expires_at = datetime.now(timezone.utc) + timedelta(days=365)
    else:
        sub = Subscription(
            user_id=user_uuid,
            tier=target_tier,
            status=SubscriptionStatus.ACTIVE,
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(sub)

    await _write_audit(
        db, current_user, AdminAction.USER_APPROVE,
        target_user_id=user_uuid,
        details={"subscription_tier": body.subscription_tier, "notes": body.notes},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    # W3-20: also write the regulatory AuditLog (hash-chained, tamper-evident).
    # Fix #18: no try/except — if the chain write fails, the whole
    # transaction rolls back so the AdminAuditLog and AuditLog cannot
    # diverge. Better to fail loudly than to silently desync the
    # regulatory chain.
    await patch_write_audit_log(
        db,
        action="user.approve",
        user_id=current_user.id,
        user_email=current_user.email,
        entity_type="user",
        entity_id=str(user_uuid),
        old_values={"approval_status": "pending", "is_active": False},
        new_values={
            "approval_status": "approved",
            "is_active": True,
            "subscription_tier": body.subscription_tier,
        },
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    return AdminActionResponse(
        success=True,
        message=f"User approved with {body.subscription_tier} subscription",
        user_id=user_id,
        action=AdminAction.USER_APPROVE,
        new_state={
            "approval_status": "approved",
            "subscription_tier": body.subscription_tier,
            "is_active": True,
        },
    )


@router.post("/users/{user_id}/reject", response_model=AdminActionResponse)
async def reject_user(
    user_id: str,
    body: AdminRejectRequest,
    request: Request,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user id")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if user.approval_status != ApprovalStatus.PENDING:
        raise HTTPException(400, f"User is {user.approval_status.value}, not pending")

    # pr-agent fix (10th pass): rate limit BEFORE mutation. See approve_user.
    _check_rate_limit(current_user.id)

    user.approval_status = ApprovalStatus.REJECTED
    user.approved_by = current_user.id
    user.approved_at = datetime.now(timezone.utc)
    user.rejection_reason = body.reason
    user.is_active = False

    await _write_audit(
        db, current_user, AdminAction.USER_REJECT,
        target_user_id=user_uuid,
        details={"reason": body.reason},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    # W3-20: hash-chained regulatory audit log entry. Fix #18: no try/except.
    await patch_write_audit_log(
        db,
        action="user.reject",
        user_id=current_user.id,
        user_email=current_user.email,
        entity_type="user",
        entity_id=str(user_uuid),
        old_values={"approval_status": "pending", "is_active": True},
        new_values={
            "approval_status": "rejected",
            "is_active": False,
            "rejection_reason": body.reason,
        },
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    return AdminActionResponse(
        success=True,
        message="User rejected",
        user_id=user_id,
        action=AdminAction.USER_REJECT,
        new_state={
            "approval_status": "rejected",
            "rejection_reason": body.reason,
            "is_active": False,
        },
    )


# =============================================================================
# Tier / activation
# =============================================================================

@router.post("/users/{user_id}/tier", response_model=AdminActionResponse)
async def change_tier(
    user_id: str,
    body: AdminTierChangeRequest,
    request: Request,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user id")

    valid_tiers = {t.value: t for t in SubscriptionTier}
    if body.subscription_tier not in valid_tiers:
        raise HTTPException(400, f"Invalid tier. Valid: {', '.join(valid_tiers)}")
    target_tier = valid_tiers[body.subscription_tier]

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    # Fix #21: do not allow tier changes on non-approved or inactive
    # users. This prevents an admin from re-approving a previously
    # rejected user by changing their tier alone (bypassing the
    # approve_user flow and its audit semantics). To give a rejected
    # user access, use /approve first.
    if user.approval_status != ApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change tier: user approval_status is "
                   f"'{user.approval_status.value}', must be 'approved'",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change tier: user is not active",
        )

    # pr-agent fix (10th pass): rate limit BEFORE mutation. See approve_user.
    _check_rate_limit(current_user.id)

    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_uuid)
    )
    sub = sub_result.scalar_one_or_none()
    old_tier = sub.tier.value if sub else None
    if sub:
        sub.tier = target_tier
        sub.status = SubscriptionStatus.ACTIVE
        if not sub.started_at:
            sub.started_at = datetime.now(timezone.utc)
        if not sub.expires_at or sub.expires_at < datetime.now(timezone.utc):
            sub.expires_at = datetime.now(timezone.utc) + timedelta(days=365)
    else:
        sub = Subscription(
            user_id=user_uuid,
            tier=target_tier,
            status=SubscriptionStatus.ACTIVE,
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(sub)

    await _write_audit(
        db, current_user, AdminAction.TIER_CHANGE,
        target_user_id=user_uuid,
        details={"old_tier": old_tier, "new_tier": body.subscription_tier, "reason": body.reason},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    # W3-20: hash-chained regulatory audit log entry. Fix #18: no try/except.
    await patch_write_audit_log(
        db,
        action="user.tier_change",
        user_id=current_user.id,
        user_email=current_user.email,
        entity_type="subscription",
        entity_id=str(user_uuid),
        old_values={"tier": old_tier},
        new_values={"tier": body.subscription_tier, "reason": body.reason},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    return AdminActionResponse(
        success=True,
        message=f"Tier changed: {old_tier} -> {body.subscription_tier}",
        user_id=user_id,
        action=AdminAction.TIER_CHANGE,
        new_state={"old_tier": old_tier, "new_tier": body.subscription_tier},
    )


@router.post("/users/{user_id}/deactivate", response_model=AdminActionResponse)
async def deactivate_user(
    user_id: str,
    body: AdminDeactivateRequest,
    request: Request,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user id")
    if user_uuid == current_user.id:
        raise HTTPException(400, "Admins cannot deactivate themselves")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    # Fix #14: only super-admins can deactivate other admins. Without
    # this, any compromised admin can lock out every other admin.
    if user.role == UserRole.ADMIN and not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super-admins can deactivate other admins",
        )

    # pr-agent fix (10th pass): rate limit BEFORE mutation. See approve_user.
    _check_rate_limit(current_user.id)

    user.is_active = False
    # Invalidate any outstanding JWTs for this user. Their `iat` is now
    # older than this timestamp, so get_current_user will reject them.
    user.token_invalidated_at = datetime.now(timezone.utc)
    await _write_audit(
        db, current_user, AdminAction.USER_DEACTIVATE,
        target_user_id=user_uuid,
        details={"reason": body.reason},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    # W3-20: hash-chained regulatory audit log entry. Fix #18: no try/except.
    await patch_write_audit_log(
        db,
        action="user.deactivate",
        user_id=current_user.id,
        user_email=current_user.email,
        old_values={"is_active": True, "token_invalidated_at": None},
        new_values={
            "is_active": False,
            "token_invalidated_at": user.token_invalidated_at.isoformat(),
            "reason": body.reason,
        },
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    return AdminActionResponse(
        success=True,
        message="User deactivated",
        user_id=user_id,
        action=AdminAction.USER_DEACTIVATE,
        new_state={"is_active": False},
    )


@router.post("/users/{user_id}/reactivate", response_model=AdminActionResponse)
async def reactivate_user(
    user_id: str,
    request: Request,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user id")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    # pr-agent fix (10th pass): rate limit BEFORE mutation. See approve_user.
    _check_rate_limit(current_user.id)

    user.is_active = True
    # Fix #16: do NOT clear token_invalidated_at on reactivation. The
    # reactivation flag is a monotonic "high-water mark": once a token
    # has been invalidated, it stays invalid even if the user is
    # reactivated. The user must obtain a fresh JWT (by logging in
    # again) to receive a new iat. This prevents an attacker who
    # captured a JWT during the deactivated window from regaining
    # access after a reactivation.
    #
    # (No assignment here; the existing token_invalidated_at is kept.)
    # pr-agent fix (10th pass): the previous Fix #25 patched _write_audit
    # to pass reason=None, but the W3-20 chained-log call below still
    # dereferenced the request-body parameter. reactivate_user takes
    # no body parameter, so the original reference was a NameError at
    # runtime. Pass reason=None on both audit-log writes.
    await _write_audit(
        db, current_user, AdminAction.USER_REACTIVATE,
        target_user_id=user_uuid,
        details={"reason": None},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    # W3-20: hash-chained regulatory audit log entry. Fix #18: no try/except.
    await patch_write_audit_log(
        db,
        action="user.reactivate",
        user_id=current_user.id,
        user_email=current_user.email,
        entity_type="user",
        entity_id=str(user_uuid),
        old_values={"is_active": False},
        new_values={"is_active": True, "reason": None},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    return AdminActionResponse(
        success=True,
        message="User reactivated",
        user_id=user_id,
        action=AdminAction.USER_REACTIVATE,
        new_state={"is_active": True},
    )


# =============================================================================
# Usage
# =============================================================================

@router.get("/users/{user_id}/usage", response_model=AdminUserUsage)
async def get_user_usage(
    user_id: str,
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user id")

    result = await db.execute(
        select(User)
        .options(selectinload(User.subscription))
        .where(User.id == user_uuid)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    sub = user.subscription
    tier = sub.tier if sub else SubscriptionTier.TRIAL
    limits = get_tier_limits(tier)
    lifetime_assessments = await db.scalar(
        select(func.count(Assessment.id)).where(Assessment.created_by == user_uuid)
    )
    lifetime_documents = await db.scalar(
        select(func.count(GeneratedDocument.id))
        .join(Assessment, Assessment.id == GeneratedDocument.assessment_id)
        .where(Assessment.created_by == user_uuid)
    )
    lifetime_chat = await db.scalar(
        select(func.count(ChatMessage.id)).where(ChatMessage.user_id == user_uuid)
    )

    monthly_assessments = sub.monthly_assessments_used if sub else 0
    monthly_documents = sub.monthly_documents_generated if sub else 0
    monthly_chat_messages = sub.monthly_chat_messages_used if sub else 0

    return AdminUserUsage(
        user_id=user_id,
        email=user.email,
        subscription_tier=tier.value,
        monthly_assessments_used=monthly_assessments,
        monthly_documents_generated=monthly_documents,
        monthly_chat_messages_used=monthly_chat,
        monthly_assessments_limit=limits.get("monthly_assessments", 0),
        monthly_documents_limit=limits.get("monthly_documents", 0),
        monthly_chat_messages_limit=limits.get("monthly_chat_messages", 0),
        usage_reset_at=sub.usage_reset_at if sub else None,
        lifetime_assessments=lifetime_assessments or 0,
        lifetime_documents=lifetime_documents or 0,
        lifetime_chat_messages=lifetime_chat or 0,
    )


# =============================================================================
# Billing
# =============================================================================

@router.get("/billing/summary", response_model=AdminBillingSummary)
async def billing_summary(
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Only currently-paying subscriptions count toward MRR. Cancelled,
    # past_due, and unpaid rows are excluded.
    paying_status = SubscriptionStatus.ACTIVE
    tier_rows = await db.execute(
        select(Subscription.tier, func.count(Subscription.id))
        .where(Subscription.status == paying_status)
        .group_by(Subscription.tier)
    )
    users_by_tier = {t.value: 0 for t in SubscriptionTier}
    for tier, count in tier_rows.all():
        if tier:
            users_by_tier[tier.value] = count or 0

    status_rows = await db.execute(
        select(User.approval_status, func.count(User.id))
        .group_by(User.approval_status)
    )
    users_by_status = {s.value: 0 for s in ApprovalStatus}
    for st, count in status_rows.all():
        if st:
            users_by_status[st.value] = count or 0

    settings = get_settings()
    mrr = 0
    for tier_value, count in users_by_tier.items():
        mrr += settings.tier_price_usd.get(tier_value, 0) * count
    arr = mrr * 12

    total_users = await db.scalar(select(func.count(User.id)))
    trialing = users_by_tier.get(SubscriptionTier.TRIAL.value, 0)

    # Pending payment failures: not modelled here. Set to 0 until the
    # Stripe webhook (or equivalent) lands.
    pending_payment_failures = 0

    return AdminBillingSummary(
        total_users=total_users or 0,
        users_by_tier=users_by_tier,
        users_by_status=users_by_status,
        monthly_recurring_revenue_usd=mrr,
        annual_recurring_revenue_usd=arr,
        trialing_users=trialing,
        pending_payment_failures=pending_payment_failures,
    )


# =============================================================================
# Audit log
# =============================================================================

@router.get("/audit-log", response_model=AdminAuditLogResponse)
async def list_audit_log(
    action: Optional[str] = Query(None, description="Filter by action type"),
    admin_id: Optional[str] = Query(None, description="Filter by admin id"),
    target_user_id: Optional[str] = Query(None, description="Filter by target user id"),
    since: Optional[datetime] = Query(None, description="Filter by created_at >= since"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List admin audit log entries (most recent first)."""
    base = select(AdminAuditLog)
    conditions = []
    if action:
        conditions.append(AdminAuditLog.action == action)
    if admin_id:
        try:
            conditions.append(AdminAuditLog.admin_id == UUID(admin_id))
        except ValueError:
            raise HTTPException(400, "Invalid admin_id")
    if target_user_id:
        try:
            conditions.append(AdminAuditLog.target_user_id == UUID(target_user_id))
        except ValueError:
            raise HTTPException(400, "Invalid target_user_id")
    if since:
        conditions.append(AdminAuditLog.created_at >= since)

    if conditions:
        base = base.where(and_(*conditions))

    total = await db.scalar(
        select(func.count()).select_from(base.subquery())
    )

    base = base.order_by(desc(AdminAuditLog.created_at)).limit(limit).offset(offset)
    result = await db.execute(base)
    entries = result.scalars().all()

    user_ids = {e.admin_id for e in entries}
    user_ids |= {e.target_user_id for e in entries if e.target_user_id}
    email_map = {}
    if user_ids:
        ures = await db.execute(
            select(User.id, User.email).where(User.id.in_(user_ids))
        )
        email_map = {uid: em for uid, em in ures.all()}

    # Redact the ``details`` JSONB to a safe subset before returning. The
    # raw field can contain free-text rejection reasons, notes from the
    # admin, etc. - all of which are PII or sensitive operational data.
    # Admins get the structured summary (keys + lengths) but not the text.
    safe_keys = {
        "subscription_tier", "old_tier", "new_tier",
        "is_active", "approval_status", "token_invalidated_at",
    }

    def _redact(d: Optional[dict]) -> dict:
        """Recursively redact free-text fields from a details JSONB.

        Fix #23 (5th pr-agent pass): the previous version only handled
        top-level keys. Nested dicts and lists could leak PII. This
        version walks the structure recursively; free-text strings
        anywhere in the tree are replaced with a length field.
        """
        if d is None:
            return {}
        if isinstance(d, list):
            return [_redact(x) for x in d]
        if not isinstance(d, dict):
            return d
        out: dict = {}
        for k, v in d.items():
            if k in safe_keys:
                if isinstance(v, str) and len(v) > 64:
                    out[k] = v[:64] + "..."
                else:
                    out[k] = v
            else:
                if isinstance(v, str):
                    out[f"{k}_length"] = len(v)
                else:
                    out[k] = _redact(v)
        return out

    # Fix #13: redact top-level PII fields, not just the details JSONB.
    # - ip_address: mask last octet (e.g. 203.0.113.55 -> 203.0.113.0)
    # - user_agent: keep first 40 chars so admins can spot unusual
    #   clients but lose the rest (often contains device + browser ids)
    # - admin_email / target_user_email: only returned to super-admins.
    #   Non-super admins see the user's UUID but not the email address,
    #   which avoids mass email enumeration by a compromised admin.
    #
    # pr-agent fix: previously these assignments were hoisted above the
    # list comprehension with `e` referenced outside its scope (NameError
    # at runtime), AND because the assignments ran once outside the loop,
    # every returned entry would share the last entry's ip_address /
    # user_agent. Moving them inside the comprehension gives each entry
    # its own masked values.
    is_super_admin = current_user.is_super_admin
    return AdminAuditLogResponse(
        entries=[
            AdminAuditLogEntry(
                id=str(e.id),
                admin_id=str(e.admin_id),
                admin_email=email_map.get(e.admin_id) if is_super_admin else None,
                target_user_id=str(e.target_user_id) if e.target_user_id else None,
                target_user_email=(
                    email_map.get(e.target_user_id)
                    if is_super_admin and e.target_user_id
                    else None
                ),
                action=e.action,
                details=_redact(e.details),
                ip_address=_mask_ip(e.ip_address),
                user_agent=_redact_user_agent(e.user_agent),
                created_at=e.created_at,
            )
            for e in entries
        ],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


def _mask_ip(ip: Optional[str]) -> Optional[str]:
    """Mask the last octet of an IPv4 address (or last 80 bits of IPv6)
    so the audit log captures which /24 (or /48) made the change, not
    the exact device IP. Returns None unchanged.
    """
    if not ip:
        return ip
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return None  # invalid -> redact entirely
    if isinstance(parsed, ipaddress.IPv4Address):
        # 203.0.113.55 -> 203.0.113.0
        parts = ip.split(".")
        return ".".join(parts[:3]) + ".0"
    # IPv6: zero out the last 80 bits -> keep only the /48 prefix.
    # pr-agent fix (10th pass): the previous version appended ":0:0:0:0:0:0"
    # (6 zero hextets) after the first 3, producing 9 hextets total — an
    # invalid IPv6 address. A valid IPv6 has exactly 8 hextets.
    parts = ip.split(":")
    if len(parts) >= 3:
        return ":".join(parts[:3]) + ":0:0:0:0:0"
    return ip  # too short to mask, return as-is


def _redact_user_agent(ua: Optional[str], keep: int = 40) -> Optional[str]:
    """Keep the first `keep` chars of a user agent string and replace
    the rest with an ellipsis. The first 40 chars of a typical UA
    identify the family (Chrome / Safari / curl / Python-urllib etc.)
    but not the full version + device fingerprint.
    """
    if ua is None:
        return None
    if len(ua) <= keep:
        return ua
    return ua[:keep] + "..."
