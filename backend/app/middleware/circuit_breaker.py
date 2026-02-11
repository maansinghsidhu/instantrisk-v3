"""
Circuit Breaker Middleware

Provides global cost protection by monitoring API usage and automatically
disabling expensive operations if thresholds are exceeded.

Prevents bill attacks and runaway costs from bugs or attacks.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable, Any
from enum import Enum
import asyncio
import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("security.circuit_breaker")

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


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CostCategory(str, Enum):
    """Categories of cost-generating operations."""
    AI_API = "ai_api"           # OpenAI, MiniMax, etc.
    DOCUMENT_OCR = "document_ocr"  # OCR processing
    STORAGE = "storage"         # S3/MinIO operations
    TOTAL = "total"             # Total across all


# Global thresholds (configurable via environment)
THRESHOLDS = {
    # Hourly limits
    "hourly": {
        CostCategory.AI_API: 500,        # Max 500 AI API calls/hour
        CostCategory.DOCUMENT_OCR: 200,   # Max 200 OCR operations/hour
        CostCategory.STORAGE: 1000,       # Max 1000 storage ops/hour
        CostCategory.TOTAL: 2000,         # Max 2000 total ops/hour
    },
    # Daily cost limits (in cents to avoid float issues)
    "daily_cost_cents": {
        CostCategory.AI_API: 5000,        # $50/day AI API
        CostCategory.DOCUMENT_OCR: 1000,  # $10/day OCR
        CostCategory.STORAGE: 500,        # $5/day storage
        CostCategory.TOTAL: 10000,        # $100/day total
    },
}

# Estimated cost per operation (in cents)
COST_PER_OPERATION = {
    CostCategory.AI_API: 2,           # ~$0.02 per AI call
    CostCategory.DOCUMENT_OCR: 1,     # ~$0.01 per OCR
    CostCategory.STORAGE: 0.1,        # ~$0.001 per storage op
}


def _get_hourly_key(category: CostCategory) -> str:
    """Generate Redis key for hourly tracking."""
    hour = datetime.utcnow().strftime("%Y-%m-%d-%H")
    return f"circuit:hourly:{category.value}:{hour}"


def _get_daily_cost_key(category: CostCategory) -> str:
    """Generate Redis key for daily cost tracking."""
    day = datetime.utcnow().strftime("%Y-%m-%d")
    return f"circuit:daily_cost:{category.value}:{day}"


def _get_circuit_state_key(category: CostCategory) -> str:
    """Generate Redis key for circuit state."""
    return f"circuit:state:{category.value}"


async def record_operation(
    category: CostCategory,
    count: int = 1,
    cost_cents: Optional[int] = None
) -> bool:
    """
    Record an operation and check if circuit should trip.

    Args:
        category: Cost category
        count: Number of operations
        cost_cents: Optional explicit cost in cents

    Returns:
        True if operation is allowed, False if circuit is open
    """
    redis = await get_redis()

    # Check if circuit is already open
    state = await get_circuit_state(category)
    if state == CircuitState.OPEN:
        logger.warning(f"Circuit OPEN for {category.value}, blocking operation")
        return False

    # Record hourly count
    hourly_key = _get_hourly_key(category)
    hourly_count = await redis.incrby(hourly_key, count)
    await redis.expire(hourly_key, 3600)  # 1 hour expiry

    # Record daily cost
    cost = cost_cents if cost_cents else int(COST_PER_OPERATION.get(category, 0) * count)
    daily_key = _get_daily_cost_key(category)
    daily_cost = await redis.incrby(daily_key, cost)
    await redis.expire(daily_key, 86400)  # 24 hour expiry

    # Also track total
    if category != CostCategory.TOTAL:
        await record_operation(CostCategory.TOTAL, count, cost)

    # Check thresholds
    hourly_limit = THRESHOLDS["hourly"].get(category, float('inf'))
    daily_cost_limit = THRESHOLDS["daily_cost_cents"].get(category, float('inf'))

    if hourly_count >= hourly_limit:
        await trip_circuit(category, f"Hourly limit exceeded: {hourly_count}/{hourly_limit}")
        return False

    if daily_cost >= daily_cost_limit:
        await trip_circuit(category, f"Daily cost limit exceeded: ${daily_cost/100:.2f}/${daily_cost_limit/100:.2f}")
        return False

    # Warning at 80% threshold
    if hourly_count >= hourly_limit * 0.8:
        logger.warning(f"Circuit warning: {category.value} at {hourly_count}/{hourly_limit} hourly")

    if daily_cost >= daily_cost_limit * 0.8:
        logger.warning(f"Circuit warning: {category.value} at ${daily_cost/100:.2f}/${daily_cost_limit/100:.2f} daily")

    return True


async def trip_circuit(category: CostCategory, reason: str, duration_minutes: int = 60) -> None:
    """
    Trip the circuit breaker (open it).

    Args:
        category: Cost category
        reason: Reason for tripping
        duration_minutes: How long to keep circuit open
    """
    redis = await get_redis()

    state_key = _get_circuit_state_key(category)
    await redis.setex(state_key, duration_minutes * 60, CircuitState.OPEN.value)

    logger.critical(
        f"CIRCUIT BREAKER TRIPPED: {category.value}, "
        f"reason: {reason}, duration: {duration_minutes}min"
    )

    # TODO: Send alert (email, Slack, PagerDuty, etc.)
    # await send_alert(f"Circuit breaker tripped: {category.value}", reason)


async def get_circuit_state(category: CostCategory) -> CircuitState:
    """Get current circuit state."""
    redis = await get_redis()
    state_key = _get_circuit_state_key(category)
    state = await redis.get(state_key)

    if state:
        return CircuitState(state)
    return CircuitState.CLOSED


async def reset_circuit(category: CostCategory) -> None:
    """Manually reset (close) a circuit."""
    redis = await get_redis()
    state_key = _get_circuit_state_key(category)
    await redis.delete(state_key)
    logger.info(f"Circuit manually reset: {category.value}")


async def get_circuit_stats() -> Dict:
    """Get current circuit breaker statistics."""
    redis = await get_redis()
    stats = {}

    for category in CostCategory:
        hourly_key = _get_hourly_key(category)
        daily_key = _get_daily_cost_key(category)

        hourly_count = await redis.get(hourly_key)
        daily_cost = await redis.get(daily_key)
        state = await get_circuit_state(category)

        hourly_limit = THRESHOLDS["hourly"].get(category, 0)
        daily_limit = THRESHOLDS["daily_cost_cents"].get(category, 0)

        stats[category.value] = {
            "state": state.value,
            "hourly_count": int(hourly_count) if hourly_count else 0,
            "hourly_limit": hourly_limit,
            "hourly_remaining": max(0, hourly_limit - (int(hourly_count) if hourly_count else 0)),
            "daily_cost_cents": int(daily_cost) if daily_cost else 0,
            "daily_cost_limit_cents": daily_limit,
            "daily_cost_remaining_cents": max(0, daily_limit - (int(daily_cost) if daily_cost else 0)),
        }

    return stats


class CircuitOpenError(Exception):
    """Raised when circuit is open and operation is blocked."""

    def __init__(self, category: CostCategory, message: str = ""):
        self.category = category
        super().__init__(
            f"Circuit breaker open for {category.value}. "
            f"Service temporarily unavailable. {message}"
        )


# Decorator for protecting expensive operations
def protected_operation(category: CostCategory, cost_cents: int = None):
    """
    Decorator to protect expensive operations with circuit breaker.

    Usage:
        @protected_operation(CostCategory.AI_API)
        async def call_openai(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs) -> Any:
            # Check circuit before operation
            allowed = await record_operation(category, cost_cents=cost_cents)
            if not allowed:
                raise CircuitOpenError(category)

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Could track errors here for more sophisticated circuit logic
                raise

        return wrapper
    return decorator
