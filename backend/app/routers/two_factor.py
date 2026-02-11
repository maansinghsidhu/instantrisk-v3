"""
InstantRisk V2 - Two-Factor Authentication Router

This module provides 2FA endpoints for setup, verification, and management.
Uses PyOTP for TOTP (Time-based One-Time Password) compatible with
Google Authenticator, Microsoft Authenticator, Authy, and other TOTP apps.
"""

import json
import secrets
import hashlib
from io import BytesIO
import base64

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, verify_password
from app.models.user import User


router = APIRouter()


# =============================================================================
# Pydantic Models
# =============================================================================

class TwoFASetupResponse(BaseModel):
    """Response model for 2FA setup."""
    secret: str
    qr_code: str  # Base64 encoded QR code image
    manual_entry_key: str
    issuer: str = "InstantRisk"


class TwoFAVerifyRequest(BaseModel):
    """Request model for 2FA verification."""
    code: str


class TwoFAVerifyResponse(BaseModel):
    """Response model for 2FA verification."""
    success: bool
    backup_codes: list[str] | None = None
    message: str


class TwoFADisableRequest(BaseModel):
    """Request model for disabling 2FA."""
    password: str
    code: str


class TwoFAStatusResponse(BaseModel):
    """Response model for 2FA status."""
    enabled: bool
    has_backup_codes: bool


# =============================================================================
# Helper Functions
# =============================================================================

def generate_qr_code(provisioning_uri: str) -> str:
    """Generate a QR code image and return as base64 string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate a list of backup codes."""
    return [secrets.token_hex(4).upper() for _ in range(count)]


def hash_backup_code(code: str) -> str:
    """Hash a backup code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/status", response_model=TwoFAStatusResponse)
async def get_2fa_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get current 2FA status for the authenticated user.

    Returns:
        dict: 2FA enabled status and whether backup codes exist.
    """
    return {
        "enabled": current_user.two_fa_enabled or False,
        "has_backup_codes": bool(current_user.two_fa_backup_codes)
    }


@router.post("/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Initialize 2FA setup for the current user.

    Generates a TOTP secret and returns a QR code for scanning
    with an authenticator app (Google Authenticator, Microsoft Authenticator, etc.).

    Note: 2FA is not enabled until the user verifies a code via /2fa/verify.

    Returns:
        dict: Secret key, QR code image (base64), and manual entry key.
    """
    if current_user.two_fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled. Disable it first to set up again."
        )

    # Generate a new TOTP secret
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)

    # Create provisioning URI for authenticator apps
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="InstantRisk"
    )

    # Generate QR code
    qr_code_base64 = generate_qr_code(provisioning_uri)

    # Store secret temporarily (not enabled yet)
    current_user.two_fa_secret = secret
    await db.commit()

    return {
        "secret": secret,
        "qr_code": qr_code_base64,
        "manual_entry_key": secret,
        "issuer": "InstantRisk"
    }


@router.post("/verify", response_model=TwoFAVerifyResponse)
async def verify_2fa(
    request: TwoFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Verify a TOTP code and enable 2FA.

    This endpoint is used during initial 2FA setup to verify the user
    has correctly configured their authenticator app.

    Args:
        request: Contains the 6-digit TOTP code from the authenticator app.

    Returns:
        dict: Success status and backup codes (only shown once).
    """
    if not current_user.two_fa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA setup not started. Call /2fa/setup first."
        )

    if current_user.two_fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled."
        )

    # Verify the code
    totp = pyotp.TOTP(current_user.two_fa_secret)
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please try again."
        )

    # Generate backup codes
    backup_codes = generate_backup_codes(10)
    hashed_codes = [hash_backup_code(code) for code in backup_codes]

    # Enable 2FA and store hashed backup codes
    current_user.two_fa_enabled = True
    current_user.two_fa_backup_codes = json.dumps(hashed_codes)
    await db.commit()

    return {
        "success": True,
        "backup_codes": backup_codes,  # Only shown once!
        "message": "2FA has been enabled successfully. Save your backup codes securely."
    }


@router.post("/disable", response_model=TwoFAVerifyResponse)
async def disable_2fa(
    request: TwoFADisableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Disable 2FA for the current user.

    Requires both password and a valid TOTP code for security.

    Args:
        request: Contains password and current TOTP code.

    Returns:
        dict: Success status and confirmation message.
    """
    if not current_user.two_fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled."
        )

    # Verify password
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password."
        )

    # Verify TOTP code
    totp = pyotp.TOTP(current_user.two_fa_secret)
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code."
        )

    # Disable 2FA
    current_user.two_fa_enabled = False
    current_user.two_fa_secret = None
    current_user.two_fa_backup_codes = None
    await db.commit()

    return {
        "success": True,
        "backup_codes": None,
        "message": "2FA has been disabled successfully."
    }


@router.post("/regenerate-backup-codes", response_model=TwoFAVerifyResponse)
async def regenerate_backup_codes(
    request: TwoFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Regenerate backup codes (requires valid TOTP code).

    Invalidates all existing backup codes.

    Args:
        request: Contains current TOTP code for verification.

    Returns:
        dict: New backup codes (only shown once).
    """
    if not current_user.two_fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled."
        )

    # Verify TOTP code
    totp = pyotp.TOTP(current_user.two_fa_secret)
    if not totp.verify(request.code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code."
        )

    # Generate new backup codes
    backup_codes = generate_backup_codes(10)
    hashed_codes = [hash_backup_code(code) for code in backup_codes]

    current_user.two_fa_backup_codes = json.dumps(hashed_codes)
    await db.commit()

    return {
        "success": True,
        "backup_codes": backup_codes,
        "message": "Backup codes have been regenerated. Save them securely."
    }


# =============================================================================
# Login 2FA Verification (called from auth router)
# =============================================================================

async def verify_2fa_code(user: User, code: str, db: AsyncSession) -> bool:
    """
    Verify a 2FA code (TOTP or backup code) for login.

    Args:
        user: User attempting to log in.
        code: The 6-digit TOTP code or backup code.
        db: Database session.

    Returns:
        bool: True if code is valid.
    """
    if not user.two_fa_secret:
        return False

    # Try TOTP verification first
    totp = pyotp.TOTP(user.two_fa_secret)
    if totp.verify(code, valid_window=1):
        return True

    # Try backup code
    if user.two_fa_backup_codes:
        hashed_codes = json.loads(user.two_fa_backup_codes)
        code_hash = hash_backup_code(code.upper())

        if code_hash in hashed_codes:
            # Remove used backup code
            hashed_codes.remove(code_hash)
            user.two_fa_backup_codes = json.dumps(hashed_codes)
            await db.commit()
            return True

    return False
