"""
Rate Limiting Middleware

Uses slowapi (built on limits library) for FastAPI-native rate limiting.
Protects against brute force attacks and API abuse.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("security.rate_limit")

# Create limiter with IP-based key function
limiter = Limiter(key_func=get_remote_address)


# Rate limit configurations by endpoint type
class RateLimits:
    """Rate limit configurations for different endpoint types."""

    # Authentication - strict limits to prevent brute force
    LOGIN = "60/minute"              # 5 login attempts per minute
    REGISTER = "3/hour"             # 3 registrations per hour per IP
    TWO_FA_VERIFY = "5/minute"      # 5 2FA attempts per minute
    PASSWORD_RESET = "3/hour"       # 3 password reset requests per hour

    # AI/Expensive operations - protect API costs
    CHAT = "30/minute"              # 30 chat messages per minute
    ANALYSIS_START = "5/hour"       # 5 analyses per hour
    DOCUMENT_EXTRACT = "20/hour"    # 20 document extractions per hour

    # File operations
    UPLOAD = "20/hour"              # 20 file uploads per hour

    # General API
    DEFAULT = "100/minute"          # 100 requests per minute default
    SEARCH = "60/minute"            # 60 search requests per minute

    # Health checks - lenient
    HEALTH = "1000/minute"          # Health checks are OK


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.
    Logs the event and returns a clean error response.
    """
    client_ip = get_remote_address(request)
    endpoint = request.url.path

    logger.warning(
        f"Rate limit exceeded: IP={client_ip}, endpoint={endpoint}, "
        f"limit={exc.detail}"
    )

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please try again later.",
            "retry_after": getattr(exc, "retry_after", 60),
        },
        headers={
            "Retry-After": str(getattr(exc, "retry_after", 60)),
            "X-RateLimit-Limit": str(exc.detail) if exc.detail else "unknown",
        }
    )


def get_user_identifier(request: Request) -> str:
    """
    Get user identifier for rate limiting.
    Uses user ID if authenticated, otherwise IP address.
    """
    # Try to get user from request state (set by auth middleware)
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        return f"user:{user.id}"

    # Fall back to IP address
    return f"ip:{get_remote_address(request)}"


# Decorator shortcuts for common rate limits
def limit_login(func):
    """Apply login rate limit."""
    return limiter.limit(RateLimits.LOGIN)(func)


def limit_register(func):
    """Apply registration rate limit."""
    return limiter.limit(RateLimits.REGISTER)(func)


def limit_chat(func):
    """Apply chat rate limit."""
    return limiter.limit(RateLimits.CHAT)(func)


def limit_analysis(func):
    """Apply analysis rate limit."""
    return limiter.limit(RateLimits.ANALYSIS_START)(func)


def limit_upload(func):
    """Apply upload rate limit."""
    return limiter.limit(RateLimits.UPLOAD)(func)
