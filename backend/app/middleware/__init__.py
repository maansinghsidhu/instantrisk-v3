"""
InstantRisk V5 - Security Middleware

Enterprise-grade security components:
- Rate limiting (slowapi)
- Security headers (HSTS, CSP, X-Frame-Options)
- IP protection (auto-banning, blocklists)
- Usage tracking (per-user quotas)
- Circuit breaker (cost protection)
- Security logging (structured audit logs)
"""

from .rate_limiter import limiter, rate_limit_exceeded_handler, RateLimits
from .security_headers import SecurityHeadersMiddleware
from .ip_protection import (
    IPProtectionMiddleware,
    track_failed_attempt,
    ban_ip,
    unban_ip,
    is_ip_banned,
    clear_failed_attempts,
)
from .usage_tracker import (
    UsageType,
    track_usage,
    check_quota,
    get_usage_stats,
    QuotaExceededError,
)
from .circuit_breaker import (
    CostCategory,
    CircuitState,
    record_operation,
    get_circuit_state,
    get_circuit_stats,
    trip_circuit,
    reset_circuit,
    CircuitOpenError,
    protected_operation,
)
from .security_logger import (
    SecurityEventType,
    log_security_event,
    log_login_success,
    log_login_failure,
    log_rate_limit_exceeded,
    log_ip_banned,
    log_file_blocked,
    log_malware_detected,
    log_suspicious_activity,
    log_circuit_breaker_tripped,
)

__all__ = [
    # Rate Limiter
    "limiter",
    "rate_limit_exceeded_handler",
    "RateLimits",

    # Security Headers
    "SecurityHeadersMiddleware",

    # IP Protection
    "IPProtectionMiddleware",
    "track_failed_attempt",
    "ban_ip",
    "unban_ip",
    "is_ip_banned",
    "clear_failed_attempts",

    # Usage Tracking
    "UsageType",
    "track_usage",
    "check_quota",
    "get_usage_stats",
    "QuotaExceededError",

    # Circuit Breaker
    "CostCategory",
    "CircuitState",
    "record_operation",
    "get_circuit_state",
    "get_circuit_stats",
    "trip_circuit",
    "reset_circuit",
    "CircuitOpenError",
    "protected_operation",

    # Security Logging
    "SecurityEventType",
    "log_security_event",
    "log_login_success",
    "log_login_failure",
    "log_rate_limit_exceeded",
    "log_ip_banned",
    "log_file_blocked",
    "log_malware_detected",
    "log_suspicious_activity",
    "log_circuit_breaker_tripped",
]
