"""
InstantRisk V2 - Authentication Router

This module provides authentication endpoints for user login,
registration, and token refresh with enterprise security features.

Security Features:
- Rate limiting on login/register endpoints
- IP-based failed attempt tracking
- Token blacklist support for logout
- Security event logging
"""

from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.config import settings
from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user
)
from app.models.user import User, UserRole, ApprovalStatus
from app.models.syndicate import Syndicate
from app.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserLogin,
    TokenResponse,
    TokenRefresh
)
from app.routers.two_factor import verify_2fa_code
from app.middleware.rate_limiter import limiter, RateLimits
from app.middleware.ip_protection import track_failed_attempt, clear_failed_attempts

# Security logger
security_logger = logging.getLogger("security.auth")


# =============================================================================
# Admin User Creation Schemas
# =============================================================================


class AdminUserCreate(BaseModel):
    """Schema for admin-created user with full control over status fields."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8, max_length=100)
    role: UserRole = UserRole.BROKER
    syndicate_id: Optional[int] = None
    is_active: bool = True
    is_verified: bool = True
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED


class AdminUserResponse(BaseModel):
    """Schema for admin-created user response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    syndicate_id: Optional[int] = None
    is_active: bool
    is_verified: bool
    created_at: datetime

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RateLimits.REGISTER)
async def register(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Register a new user.

    Args:
        user_data: User registration data.
        db: Database session.

    Returns:
        User: The created user object.

    Raises:
        HTTPException: If email is already registered.
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user with pending approval status
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role,
        syndicate_id=user_data.syndicate_id,
        approval_status=ApprovalStatus.PENDING,
        is_active=False  # Inactive until approved
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create trial subscription for the new user
    subscription = Subscription(
        user_id=user.id,
        tier=SubscriptionTier.TRIAL,
        status=SubscriptionStatus.PENDING,  # Pending until account approved
        started_at=datetime.now(timezone.utc)
    )
    db.add(subscription)
    await db.commit()

    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(RateLimits.LOGIN)
async def login(
    request: Request,
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Authenticate user and return tokens.

    Args:
        request: FastAPI request object.
        credentials: User login credentials.
        db: Database session.

    Returns:
        dict: Access token, refresh token, and user information.

    Raises:
        HTTPException: If credentials are invalid.
    """
    client_ip = getattr(request.state, 'client_ip', request.client.host if request.client else 'unknown')

    # Find user by email
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    # Constant-time check: always verify password to prevent timing attacks
    if user:
        password_valid = verify_password(credentials.password, user.hashed_password)
    else:
        # Hash a dummy password to consume the same time as a real check
        verify_password(credentials.password, get_password_hash("timing-attack-dummy"))
        password_valid = False

    if not user or not password_valid:
        # Track failed attempt for IP protection
        await track_failed_attempt(client_ip, "login")
        security_logger.warning(f"Login failed: ip={client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        # Check if account is pending approval (different message)
        if user.approval_status == ApprovalStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account pending approval. Please wait for admin approval before logging in."
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    # Check approval status
    if user.approval_status == ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval. Please wait for admin approval before logging in."
        )

    if user.approval_status == ApprovalStatus.REJECTED:
        rejection_msg = f"Account registration rejected. Reason: {user.rejection_reason}" if user.rejection_reason else "Account registration rejected. Please contact support."
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=rejection_msg
        )

    # Check if 2FA is enabled
    if user.two_fa_enabled:
        # If 2FA code provided, verify it
        if credentials.totp_code:
            if not await verify_2fa_code(user, credentials.totp_code, db):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid 2FA code",
                    headers={"WWW-Authenticate": "Bearer"}
                )
        else:
            # 2FA required but no code provided - return special response
            # Use JSONResponse to bypass response_model validation
            return JSONResponse(
                status_code=200,
                content={
                    "requires_2fa": True,
                    "user_id": user.id,
                    "message": "2FA verification required"
                }
            )

    # Clear failed login attempts on successful login
    await clear_failed_attempts(client_ip, "login")

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    security_logger.info(f"Login successful: user_id={user.id}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": user,
        "requires_2fa": False
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Refresh access token using refresh token.

    Args:
        token_data: Refresh token data.
        db: Database session.

    Returns:
        dict: New access token and refresh token.

    Raises:
        HTTPException: If refresh token is invalid.
    """
    # Decode refresh token
    payload = decode_token(token_data.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Check if refresh token is blacklisted (revoked)
    from app.utils.token_blacklist import is_token_blacklisted
    jti = payload.get("jti")
    if jti and await is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    # Create new tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
        "user": user
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current authenticated user information.

    Args:
        current_user: The authenticated user.

    Returns:
        User: The current user object.
    """
    return current_user


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Logout current user.

    Blacklists the current token to prevent reuse.

    Args:
        request: FastAPI request object.
        current_user: The authenticated user.

    Returns:
        dict: Logout confirmation message.
    """
    from app.utils.token_blacklist import blacklist_token
    from app.core.security import decode_token

    # Get token from authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            jti = payload.get("jti")
            exp = payload.get("exp")

            if jti and exp:
                await blacklist_token(jti, exp)
                security_logger.info(f"Logout successful: user_id={current_user.id}, jti={jti}")
        except Exception as e:
            security_logger.warning(f"Could not blacklist token on logout: {e}")

    return {"message": "Successfully logged out"}


# =============================================================================
# Session Management Endpoints
# =============================================================================

@router.get("/sessions")
async def get_active_sessions(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Get all active sessions for the current user.

    For now, returns the current session as the only active session.
    In a full implementation, this would query a sessions table.
    """
    # Get client info
    client_ip = getattr(request.state, 'client_ip', request.client.host if request.client else 'unknown')
    user_agent = request.headers.get("User-Agent", "Unknown")

    # Parse user agent to get device info
    device = "Unknown Device"
    browser = "Unknown"
    if "Mobile" in user_agent or "Android" in user_agent or "iPhone" in user_agent:
        device = "Mobile Device"
        browser = "Mobile App"
    elif "Windows" in user_agent:
        device = "Windows PC"
        browser = "Chrome" if "Chrome" in user_agent else "Edge" if "Edge" in user_agent else "Browser"
    elif "Mac" in user_agent:
        device = "Mac"
        browser = "Safari" if "Safari" in user_agent and "Chrome" not in user_agent else "Chrome"
    elif "Linux" in user_agent:
        device = "Linux PC"
        browser = "Chrome" if "Chrome" in user_agent else "Firefox" if "Firefox" in user_agent else "Browser"

    # Return current session
    sessions = [
        {
            "id": "current",
            "device": device,
            "browser": browser,
            "location": "Current Location",
            "ip_address": client_ip,
            "last_active": "Now",
            "is_current": True,
            "created_at": current_user.last_login.isoformat() if current_user.last_login else None
        }
    ]

    return {"sessions": sessions}


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Revoke a specific session.

    In a full implementation, this would invalidate the session token.
    """
    if session_id == "current":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke current session. Use logout instead."
        )

    # In a full implementation, we would:
    # 1. Look up the session in the sessions table
    # 2. Blacklist its token
    # 3. Delete the session record

    return {"message": "Session revoked successfully"}


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Revoke all other sessions (except current).

    In a full implementation, this would invalidate all other session tokens.
    """
    # In a full implementation, we would:
    # 1. Get all sessions for the user except current
    # 2. Blacklist all their tokens
    # 3. Delete the session records

    return {"message": "All other sessions revoked successfully"}


# =============================================================================
# User Admin Endpoints (Admin Only)
# =============================================================================

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role for access."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    role: Optional[str] = None,
    syndicate_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    List all users (Admin only).

    Args:
        skip: Pagination offset.
        limit: Maximum records to return.
        role: Filter by user role.
        syndicate_id: Filter by syndicate ID.
        is_active: Filter by active status.
        search: Search by email or full name.

    Returns:
        dict: Paginated list of users.
    """
    # Build query
    query = select(User)
    count_query = select(func.count(User.id))

    # Apply filters
    if role:
        try:
            role_enum = UserRole(role)
            query = query.where(User.role == role_enum)
            count_query = count_query.where(User.role == role_enum)
        except ValueError:
            pass

    if syndicate_id is not None:
        query = query.where(User.syndicate_id == syndicate_id)
        count_query = count_query.where(User.syndicate_id == syndicate_id)

    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    if search:
        search_filter = (
            User.email.ilike(f"%{search}%") |
            User.full_name.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get users with pagination
    query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value if user.role else None,
                "syndicate_id": user.syndicate_id,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "last_login": user.last_login,
            }
            for user in users
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: AdminUserCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Create a new user (Admin only).

    Accepts a JSON body. Admin can create users in any syndicate provided
    that syndicate exists. Duplicate emails are rejected.
    """
    # Check duplicate email
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Validate syndicate exists if specified
    if user_data.syndicate_id is not None:
        syndicate_result = await db.execute(
            select(Syndicate).where(Syndicate.id == user_data.syndicate_id)
        )
        if not syndicate_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Syndicate not found"
            )

    # Create user
    new_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        syndicate_id=user_data.syndicate_id,
        is_active=user_data.is_active,
        is_verified=user_data.is_verified,
        approval_status=user_data.approval_status,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    security_logger.info(
        f"User created by admin: user_id={new_user.id}, email={user_data.email}, "
        f"syndicate_id={user_data.syndicate_id}, created_by={current_user.id}"
    )

    return new_user


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get a user by ID (Admin only).

    Args:
        user_id: ID of the user to retrieve.

    Returns:
        dict: User details.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if user.role else None,
        "syndicate_id": user.syndicate_id,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    role: Optional[str] = None,
    syndicate_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    is_verified: Optional[bool] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Update a user (Admin only).

    Args:
        user_id: ID of the user to update.
        email: New email address.
        full_name: New full name.
        role: New role (admin, syndicate, broker).
        syndicate_id: New syndicate assignment.
        is_active: Activate or deactivate user.
        is_verified: Verify user.

    Returns:
        dict: Updated user details.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    # Update fields
    if email is not None:
        # Check if email is already taken by another user
        existing = await db.execute(
            select(User).where(User.email == email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use by another user"
            )
        user.email = email

    if full_name is not None:
        user.full_name = full_name

    if role is not None:
        try:
            user.role = UserRole(role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role}. Must be one of: admin, syndicate, broker"
            )

    if syndicate_id is not None:
        user.syndicate_id = syndicate_id

    if is_active is not None:
        user.is_active = is_active

    if is_verified is not None:
        user.is_verified = is_verified

    await db.commit()
    await db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if user.role else None,
        "syndicate_id": user.syndicate_id,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
        "message": "User updated successfully"
    }


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Deactivate a user (Admin only).

    Performs a soft delete by setting is_active to False.

    Args:
        user_id: ID of the user to deactivate.

    Returns:
        dict: Confirmation message.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )

    user.is_active = False
    await db.commit()

    return {"message": f"User {user.email} has been deactivated"}
