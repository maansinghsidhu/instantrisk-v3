"""
InstantRisk V2 - Security Utilities

This module provides JWT token handling, password hashing,
and authentication dependencies with enterprise security features.

Security Features:
- JWT tokens with unique JTI for blacklisting support
- Token blacklist checking on every request
- Bcrypt password hashing
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

# Monkey-patch passlib to work with bcrypt >= 4.0 (detect_wrap_bug uses >72 byte test string)
import passlib.handlers.bcrypt as _bcrypt_mod

_bcrypt_mod._detect_pybcrypt = lambda: False
_bcrypt_mod._detect_bcryptor = lambda: False
_orig_finalize = getattr(_bcrypt_mod._BcryptBackend, "_finalize_backend_mixin", None)


def _patched_finalize(cls, name, dryrun):
    cls._lacks_wrap_bug = True
    cls._has_2a_wraparound_bug = False
    return True


_bcrypt_mod._BcryptBackend._finalize_backend_mixin = classmethod(_patched_finalize)

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.models.user import User
from app.utils.token_blacklist import is_token_blacklisted

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token security
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.

    Args:
        plain_password: The plain text password to verify.
        hashed_password: The hashed password to compare against.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    return pwd_context.verify(plain_password[:72], hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a plain password using bcrypt.

    Args:
        password: The plain text password to hash.

    Returns:
        str: The hashed password.
    """
    return pwd_context.hash(password[:72])


def hash_password(password: str) -> str:
    """
    Alias for get_password_hash for backward compatibility.

    Args:
        password: The plain text password to hash.

    Returns:
        str: The hashed password.
    """
    return get_password_hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token with unique JTI for blacklist support.

    Args:
        data: The data to encode in the token.
        expires_delta: Optional custom expiration time.

    Returns:
        str: The encoded JWT token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    # Add unique JWT ID for blacklist support
    jti = str(uuid.uuid4())
    to_encode.update(
        {"exp": expire, "type": "access", "jti": jti, "iat": datetime.now(timezone.utc)}
    )
    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create a JWT refresh token with unique JTI for blacklist support.

    Args:
        data: The data to encode in the token.

    Returns:
        str: The encoded JWT refresh token.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    jti = str(uuid.uuid4())
    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
            "jti": jti,
            "iat": datetime.now(timezone.utc),
        }
    )
    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token to decode.

    Returns:
        dict: The decoded token payload.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency to get the current authenticated user.

    Checks:
    1. Token is valid and not expired
    2. Token is not blacklisted (for logout support)
    3. User exists and is active

    Args:
        credentials: The HTTP Bearer token credentials.
        db: The database session.

    Returns:
        User: The authenticated user object.

    Raises:
        HTTPException: If authentication fails.
    """
    token = credentials.credentials
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if token is blacklisted (logged out)
    jti = payload.get("jti")
    if jti and await is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated"
        )

    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to ensure the current user is an admin.

    Args:
        current_user: The current authenticated user.

    Returns:
        User: The admin user object.

    Raises:
        HTTPException: If the user is not an admin.
    """
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return current_user


async def get_current_syndicate_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to ensure the current user is a syndicate member or admin.

    Args:
        current_user: The current authenticated user.

    Returns:
        User: The syndicate or admin user object.

    Raises:
        HTTPException: If the user is not authorized.
    """
    if current_user.role.value not in ["syndicate", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Syndicate privileges required",
        )
    return current_user


def get_syndicate_from_email(email: str) -> Optional[dict]:
    """
    Auto-detect syndicate from email domain.

    Args:
        email: User's email address.

    Returns:
        dict: Syndicate info if domain is recognized, None otherwise.
    """
    domain = email.split("@")[-1].lower()
    return settings.syndicate_domains.get(domain)
