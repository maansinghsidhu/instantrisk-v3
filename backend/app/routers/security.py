"""
InstantRisk V5 - Security Admin Router

Provides admin endpoints for security monitoring and management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.middleware import (
    get_circuit_stats,
    reset_circuit,
    CostCategory,
    get_usage_stats,
    unban_ip,
)
from app.utils import (
    get_blacklist_stats,
    test_antivirus,
    get_captcha_config,
)

router = APIRouter()


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role for access."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("/status")
async def get_security_status(
    current_user: User = Depends(require_admin)
) -> dict:
    """
    Get overall security status.

    Returns system-wide security metrics and health status.
    """
    # Get circuit breaker stats
    circuit_stats = await get_circuit_stats()

    # Get token blacklist stats
    blacklist_stats = await get_blacklist_stats()

    # Get antivirus status
    antivirus_status = await test_antivirus()

    # Get CAPTCHA config
    captcha_config = get_captcha_config()

    return {
        "status": "healthy",
        "version": "5.0.0",
        "security_features": {
            "rate_limiting": True,
            "ip_protection": True,
            "token_blacklist": True,
            "file_validation": True,
            "antivirus": antivirus_status.get("available", False),
            "captcha": captcha_config.get("enabled", False),
            "circuit_breaker": True,
            "security_logging": True,
        },
        "circuit_breaker": circuit_stats,
        "token_blacklist": blacklist_stats,
        "antivirus": {
            "available": antivirus_status.get("available", False),
            "version": antivirus_status.get("version"),
        },
        "captcha": {
            "enabled": captcha_config.get("enabled", False),
            "provider": "mCaptcha" if captcha_config.get("enabled") else "disabled",
        },
    }


@router.get("/usage/{user_id}")
async def get_user_usage(
    user_id: str,
    current_user: User = Depends(require_admin)
) -> dict:
    """
    Get usage statistics for a specific user.

    Args:
        user_id: User ID to check

    Returns:
        Usage statistics for all tracked categories
    """
    # In production, look up user's subscription tier
    tier = "trial"  # Default, should be fetched from DB

    stats = await get_usage_stats(user_id, tier)

    return {
        "user_id": user_id,
        "tier": tier,
        "usage": stats,
    }


@router.post("/circuit-breaker/reset/{category}")
async def reset_circuit_breaker(
    category: str,
    current_user: User = Depends(require_admin)
) -> dict:
    """
    Reset a circuit breaker.

    Args:
        category: Circuit category to reset (ai_api, document_ocr, storage, total)

    Returns:
        Confirmation message
    """
    try:
        cost_category = CostCategory(category)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {[c.value for c in CostCategory]}"
        )

    await reset_circuit(cost_category)

    return {
        "message": f"Circuit breaker reset for {category}",
        "category": category,
    }


@router.post("/ip/unban/{ip_address}")
async def unban_ip_address(
    ip_address: str,
    current_user: User = Depends(require_admin)
) -> dict:
    """
    Unban an IP address.

    Args:
        ip_address: IP address to unban

    Returns:
        Confirmation message
    """
    success = await unban_ip(ip_address)

    if success:
        return {
            "message": f"IP {ip_address} has been unbanned",
            "ip": ip_address,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unban IP"
        )


@router.get("/antivirus/test")
async def test_antivirus_endpoint(
    current_user: User = Depends(require_admin)
) -> dict:
    """
    Test antivirus functionality.

    Runs EICAR test to verify ClamAV is working.
    """
    results = await test_antivirus()
    return results
