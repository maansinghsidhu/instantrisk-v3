"""
InstantRisk V2 - User Pydantic Schemas

This module defines Pydantic schemas for user-related CRUD operations
and authentication requests/responses.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.user import UserRole, SupportedLanguage, ApprovalStatus


class UserBase(BaseModel):
    """Base schema with common user fields."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)


class UserCreate(UserBase):
    """
    Schema for creating a new user.

    Attributes:
        email: User's email address (must be unique).
        full_name: User's full name.
        password: Plain text password (will be hashed).
        role: User role (defaults to broker).
        syndicate_id: Optional syndicate ID for syndicate users.
        preferred_language: User's preferred language for UI and documents.
    """
    password: str = Field(..., min_length=8, max_length=100)
    role: UserRole = UserRole.BROKER
    syndicate_id: Optional[int] = None
    preferred_language: SupportedLanguage = SupportedLanguage.ENGLISH


class UserUpdate(BaseModel):
    """
    Schema for updating an existing user.

    All fields are optional to allow partial updates.
    """
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    role: Optional[UserRole] = None
    syndicate_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    preferred_language: Optional[SupportedLanguage] = None


class UserResponse(UserBase):
    """
    Schema for user response data.

    Excludes sensitive fields like password.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: UserRole
    syndicate_id: Optional[int] = None
    is_active: bool
    is_verified: bool
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    preferred_language: SupportedLanguage = SupportedLanguage.ENGLISH
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    approved_at: Optional[datetime] = None


class UserLogin(BaseModel):
    """
    Schema for user login request.

    Attributes:
        email: User's email address.
        password: User's password.
        totp_code: Optional 2FA code from authenticator app.
    """
    email: EmailStr
    password: str
    totp_code: Optional[str] = None  # 6-digit TOTP code or backup code


class TokenResponse(BaseModel):
    """
    Schema for authentication token response.

    Attributes:
        access_token: JWT access token.
        refresh_token: JWT refresh token.
        token_type: Token type (always "bearer").
        expires_in: Access token expiration in seconds.
        user: User information.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenRefresh(BaseModel):
    """
    Schema for token refresh request.

    Attributes:
        refresh_token: The refresh token to use.
    """
    refresh_token: str


class PasswordReset(BaseModel):
    """
    Schema for password reset request.

    Attributes:
        email: User's email address.
    """
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """
    Schema for confirming password reset.

    Attributes:
        token: Password reset token.
        new_password: New password to set.
    """
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
