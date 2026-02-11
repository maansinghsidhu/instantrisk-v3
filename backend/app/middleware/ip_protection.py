"""
IP Protection Middleware

Provides IP-based security including:
- Automatic IP banning after failed attempts
- IP blocklist management
- IP reputation checking against known bad IPs
- Request tracking for abuse detection
"""

import ipaddress
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Set
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("security.ip_protection")

# Redis client for tracking
_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Get or create Redis client for IP tracking."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    return _redis_client


# Whitelisted IPs (internal services, admin IPs)
# Configure via environment variable in production
WHITELISTED_IPS: Set[str] = {
    "127.0.0.1",
    "::1",
}

# Known bad IP ranges (Spamhaus DROP list, etc.)
# Updated periodically via background task
BLOCKED_IP_RANGES: Set[ipaddress.IPv4Network] = set()


async def track_failed_attempt(ip: str, endpoint: str) -> int:
    """
    Track a failed attempt from an IP.

    Args:
        ip: Client IP address
        endpoint: The endpoint that failed (e.g., "login", "2fa")

    Returns:
        Current failure count for this IP/endpoint
    """
    redis = await get_redis()
    key = f"failed:{ip}:{endpoint}"

    try:
        count = await redis.incr(key)
        await redis.expire(key, 3600)  # 1 hour window

        logger.info(f"Failed attempt tracked: IP={ip}, endpoint={endpoint}, count={count}")

        # Auto-ban threshold
        thresholds = {
            "login": 10,      # 10 failed logins = ban
            "2fa": 10,        # 10 failed 2FA = ban
            "register": 5,    # 5 failed registrations = ban
            "default": 20,    # 20 other failures = ban
        }

        threshold = thresholds.get(endpoint, thresholds["default"])

        if count >= threshold:
            await ban_ip(ip, reason=f"Too many failures on {endpoint} ({count} attempts)")

        return count
    except Exception as e:
        logger.error(f"Failed to track attempt: {e}")
        return 0


async def ban_ip(ip: str, reason: str, duration_hours: int = 24) -> bool:
    """
    Ban an IP address.

    Args:
        ip: IP address to ban
        reason: Reason for the ban
        duration_hours: Ban duration in hours (default 24)

    Returns:
        True if ban was successful
    """
    if ip in WHITELISTED_IPS:
        logger.warning(f"Attempted to ban whitelisted IP: {ip}")
        return False

    redis = await get_redis()

    try:
        ban_data = {
            "reason": reason,
            "banned_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=duration_hours)).isoformat(),
        }

        await redis.setex(
            f"banned:{ip}",
            duration_hours * 3600,
            reason
        )

        logger.warning(f"IP banned: {ip}, reason: {reason}, duration: {duration_hours}h")
        return True
    except Exception as e:
        logger.error(f"Failed to ban IP {ip}: {e}")
        return False


async def unban_ip(ip: str) -> bool:
    """Unban an IP address."""
    redis = await get_redis()

    try:
        await redis.delete(f"banned:{ip}")
        logger.info(f"IP unbanned: {ip}")
        return True
    except Exception as e:
        logger.error(f"Failed to unban IP {ip}: {e}")
        return False


async def is_ip_banned(ip: str) -> Tuple[bool, Optional[str]]:
    """
    Check if an IP is banned.

    Returns:
        Tuple of (is_banned, reason)
    """
    redis = await get_redis()

    try:
        reason = await redis.get(f"banned:{ip}")
        if reason:
            return True, reason
        return False, None
    except Exception as e:
        logger.error(f"Failed to check ban status for {ip}: {e}")
        return False, None


def check_ip_reputation(ip: str) -> bool:
    """
    Check IP against known bad IP ranges.

    Returns:
        True if IP is clean, False if IP is in a blocked range
    """
    try:
        ip_obj = ipaddress.ip_address(ip)

        # Check against blocked ranges
        for blocked_range in BLOCKED_IP_RANGES:
            if ip_obj in blocked_range:
                logger.warning(f"IP {ip} found in blocked range {blocked_range}")
                return False

        return True
    except ValueError:
        # Invalid IP address format
        logger.warning(f"Invalid IP address format: {ip}")
        return False


async def clear_failed_attempts(ip: str, endpoint: str = "*") -> None:
    """Clear failed attempt tracking for an IP (e.g., after successful login)."""
    redis = await get_redis()

    try:
        if endpoint == "*":
            # Clear all endpoints for this IP
            keys = await redis.keys(f"failed:{ip}:*")
            if keys:
                await redis.delete(*keys)
        else:
            await redis.delete(f"failed:{ip}:{endpoint}")
    except Exception as e:
        logger.error(f"Failed to clear attempts for {ip}: {e}")


class IPProtectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for IP-based protection.

    Checks:
    1. IP not in ban list
    2. IP not in known bad IP ranges
    3. IP not exhibiting suspicious patterns
    """

    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        # Paths to exclude from IP checks (e.g., health endpoints)
        self.exclude_paths = exclude_paths or ["/health", "/", "/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        ip = self._get_client_ip(request)

        # Skip checks for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Skip checks for whitelisted IPs
        if ip in WHITELISTED_IPS:
            return await call_next(request)

        # Check if IP is banned
        is_banned, reason = await is_ip_banned(ip)
        if is_banned:
            logger.warning(f"Blocked request from banned IP: {ip}, reason: {reason}")
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Access denied. Your IP has been temporarily blocked.",
                    "reason": reason,
                }
            )

        # Check IP reputation
        if not check_ip_reputation(ip):
            logger.warning(f"Blocked request from bad reputation IP: {ip}")
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Access denied. IP blocked due to reputation.",
                }
            )

        # Store IP in request state for use in route handlers
        request.state.client_ip = ip

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """
        Get the real client IP, handling proxies.

        Checks X-Forwarded-For and X-Real-IP headers.
        """
        # Check X-Forwarded-For (set by proxies/load balancers)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP (set by Nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fall back to direct connection IP
        if request.client:
            return request.client.host

        return "unknown"


async def load_ip_blocklists() -> None:
    """
    Load IP blocklists from external sources.
    Called on startup and periodically.
    """
    global BLOCKED_IP_RANGES

    # Example: Load from Spamhaus DROP list
    # In production, fetch from:
    # - https://www.spamhaus.org/drop/drop.txt
    # - https://rules.emergingthreats.net/blockrules/compromised-ips.txt

    # For now, add some known bad ranges (examples)
    bad_ranges = [
        # Add known malicious ranges here
        # "192.0.2.0/24",  # Example
    ]

    for range_str in bad_ranges:
        try:
            BLOCKED_IP_RANGES.add(ipaddress.ip_network(range_str))
        except ValueError as e:
            logger.error(f"Invalid IP range: {range_str}, error: {e}")

    logger.info(f"Loaded {len(BLOCKED_IP_RANGES)} blocked IP ranges")
