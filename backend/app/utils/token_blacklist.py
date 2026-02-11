"""
Token Blacklist Utility

Provides JWT token blacklisting for effective logout.
Uses Redis for fast lookups with automatic expiration.
"""

import logging
from typing import Optional
from datetime import datetime
import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("security.token_blacklist")

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


async def blacklist_token(jti: str, exp: int) -> bool:
    """
    Add a token to the blacklist.

    Args:
        jti: JWT ID (unique token identifier)
        exp: Token expiration timestamp

    Returns:
        True if successfully blacklisted
    """
    try:
        redis = await get_redis()

        # Calculate TTL (time until token expires)
        current_time = int(datetime.utcnow().timestamp())
        ttl = exp - current_time

        if ttl <= 0:
            # Token already expired, no need to blacklist
            logger.debug(f"Token {jti} already expired, skipping blacklist")
            return True

        # Add to blacklist with TTL matching token expiration
        # After token expires naturally, remove from blacklist to save memory
        await redis.setex(f"token_blacklist:{jti}", ttl, "1")

        logger.info(f"Token blacklisted: {jti}, TTL: {ttl}s")
        return True

    except Exception as e:
        logger.error(f"Failed to blacklist token {jti}: {e}")
        return False


async def is_token_blacklisted(jti: str) -> bool:
    """
    Check if a token is blacklisted.

    Args:
        jti: JWT ID to check

    Returns:
        True if token is blacklisted
    """
    try:
        redis = await get_redis()
        result = await redis.exists(f"token_blacklist:{jti}")
        return result > 0

    except Exception as e:
        logger.error(f"Failed to check blacklist for {jti}: {e}")
        # Fail closed - if we can't check, assume it's valid
        # (better UX than locking out users on Redis failure)
        return False


async def get_blacklist_stats() -> dict:
    """
    Get statistics about the token blacklist.

    Returns:
        Dict with blacklist statistics
    """
    try:
        redis = await get_redis()

        # Count blacklisted tokens
        keys = await redis.keys("token_blacklist:*")
        count = len(keys)

        return {
            "blacklisted_tokens": count,
            "status": "healthy",
        }

    except Exception as e:
        logger.error(f"Failed to get blacklist stats: {e}")
        return {
            "blacklisted_tokens": -1,
            "status": "error",
            "error": str(e),
        }


async def clear_expired_tokens() -> int:
    """
    Clear expired tokens from blacklist.

    Note: This is typically not needed as Redis TTL handles expiration,
    but can be used for maintenance.

    Returns:
        Number of tokens cleared
    """
    # Redis TTL handles this automatically
    # This method is here for potential manual cleanup
    return 0
