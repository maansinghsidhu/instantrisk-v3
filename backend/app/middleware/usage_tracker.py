"""
Usage Tracker Middleware

Tracks per-user API usage and enforces quotas based on subscription tier.
Prevents bill attacks by limiting expensive operations per user.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from enum import Enum
import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("security.usage_tracker")

# Redis client
_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    return _redis_client


class UsageType(str, Enum):
    """Types of usage to track."""
    ANALYSIS = "analysis"
    CHAT_MESSAGE = "chat_message"
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_EXTRACT = "document_extract"
    AI_TOKENS = "ai_tokens"


# Quota limits by subscription tier (daily limits)
TIER_QUOTAS: Dict[str, Dict[UsageType, int]] = {
    "trial": {
        UsageType.ANALYSIS: 5,
        UsageType.CHAT_MESSAGE: 50,
        UsageType.DOCUMENT_UPLOAD: 10,
        UsageType.DOCUMENT_EXTRACT: 10,
        UsageType.AI_TOKENS: 50000,
    },
    "basic": {
        UsageType.ANALYSIS: 20,
        UsageType.CHAT_MESSAGE: 200,
        UsageType.DOCUMENT_UPLOAD: 50,
        UsageType.DOCUMENT_EXTRACT: 50,
        UsageType.AI_TOKENS: 200000,
    },
    "premium": {
        UsageType.ANALYSIS: 100,
        UsageType.CHAT_MESSAGE: 1000,
        UsageType.DOCUMENT_UPLOAD: 200,
        UsageType.DOCUMENT_EXTRACT: 200,
        UsageType.AI_TOKENS: 1000000,
    },
    "enterprise": {
        UsageType.ANALYSIS: 10000,  # Effectively unlimited
        UsageType.CHAT_MESSAGE: 100000,
        UsageType.DOCUMENT_UPLOAD: 10000,
        UsageType.DOCUMENT_EXTRACT: 10000,
        UsageType.AI_TOKENS: 100000000,
    },
}


def _get_daily_key(user_id: str, usage_type: UsageType) -> str:
    """Generate Redis key for daily usage tracking."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return f"usage:{user_id}:{usage_type.value}:{today}"


def _get_monthly_key(user_id: str, usage_type: UsageType) -> str:
    """Generate Redis key for monthly usage tracking."""
    month = datetime.utcnow().strftime("%Y-%m")
    return f"usage_monthly:{user_id}:{usage_type.value}:{month}"


async def track_usage(
    user_id: str,
    usage_type: UsageType,
    amount: int = 1
) -> Tuple[int, int]:
    """
    Track usage for a user.

    Args:
        user_id: User ID
        usage_type: Type of usage
        amount: Amount to add (default 1)

    Returns:
        Tuple of (current_usage, daily_limit)
    """
    redis = await get_redis()

    # Track daily usage
    daily_key = _get_daily_key(user_id, usage_type)
    current = await redis.incrby(daily_key, amount)

    # Set expiry to end of day (24 hours from first use)
    ttl = await redis.ttl(daily_key)
    if ttl == -1:  # No expiry set
        await redis.expire(daily_key, 86400)  # 24 hours

    # Also track monthly for reporting
    monthly_key = _get_monthly_key(user_id, usage_type)
    await redis.incrby(monthly_key, amount)
    monthly_ttl = await redis.ttl(monthly_key)
    if monthly_ttl == -1:
        await redis.expire(monthly_key, 31 * 86400)  # ~31 days

    logger.debug(f"Usage tracked: user={user_id}, type={usage_type.value}, current={current}")

    return current, 0  # Return 0 for limit, will be checked separately


async def check_quota(
    user_id: str,
    usage_type: UsageType,
    tier: str = "trial"
) -> Tuple[bool, int, int]:
    """
    Check if user has remaining quota.

    Args:
        user_id: User ID
        usage_type: Type of usage to check
        tier: Subscription tier

    Returns:
        Tuple of (allowed, current_usage, daily_limit)
    """
    redis = await get_redis()

    # Get current usage
    daily_key = _get_daily_key(user_id, usage_type)
    current = await redis.get(daily_key)
    current = int(current) if current else 0

    # Get limit for tier
    tier_lower = tier.lower()
    if tier_lower not in TIER_QUOTAS:
        tier_lower = "trial"

    limit = TIER_QUOTAS[tier_lower].get(usage_type, 0)

    allowed = current < limit

    if not allowed:
        logger.warning(
            f"Quota exceeded: user={user_id}, type={usage_type.value}, "
            f"current={current}, limit={limit}, tier={tier}"
        )

    return allowed, current, limit


async def get_usage_stats(user_id: str, tier: str = "trial") -> Dict:
    """
    Get usage statistics for a user.

    Args:
        user_id: User ID
        tier: Subscription tier

    Returns:
        Dict with usage stats for all types
    """
    redis = await get_redis()
    tier_lower = tier.lower() if tier.lower() in TIER_QUOTAS else "trial"

    stats = {}
    for usage_type in UsageType:
        daily_key = _get_daily_key(user_id, usage_type)
        monthly_key = _get_monthly_key(user_id, usage_type)

        daily = await redis.get(daily_key)
        monthly = await redis.get(monthly_key)
        limit = TIER_QUOTAS[tier_lower].get(usage_type, 0)

        stats[usage_type.value] = {
            "daily_used": int(daily) if daily else 0,
            "daily_limit": limit,
            "daily_remaining": max(0, limit - (int(daily) if daily else 0)),
            "monthly_used": int(monthly) if monthly else 0,
        }

    return stats


async def reset_daily_usage(user_id: str, usage_type: Optional[UsageType] = None) -> None:
    """
    Reset daily usage for a user (admin function).

    Args:
        user_id: User ID
        usage_type: Specific type to reset, or None for all
    """
    redis = await get_redis()

    if usage_type:
        daily_key = _get_daily_key(user_id, usage_type)
        await redis.delete(daily_key)
    else:
        for ut in UsageType:
            daily_key = _get_daily_key(user_id, ut)
            await redis.delete(daily_key)

    logger.info(f"Usage reset: user={user_id}, type={usage_type or 'all'}")


class QuotaExceededError(Exception):
    """Raised when user exceeds their usage quota."""

    def __init__(self, usage_type: UsageType, current: int, limit: int, tier: str):
        self.usage_type = usage_type
        self.current = current
        self.limit = limit
        self.tier = tier
        super().__init__(
            f"Daily quota exceeded for {usage_type.value}: "
            f"{current}/{limit} (tier: {tier})"
        )
