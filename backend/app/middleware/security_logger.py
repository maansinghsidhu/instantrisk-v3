"""
Security Event Logger

Provides structured logging for security-related events.
Integrates with structlog for consistent, queryable security logs.

Events logged:
- Authentication (login, logout, failed attempts)
- Authorization (permission denied)
- Rate limiting (exceeded)
- File uploads (blocked, scanned)
- Suspicious activity (patterns, anomalies)
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
import structlog

from app.config import settings


class SecurityEventType(str, Enum):
    """Types of security events."""
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGIN_2FA_REQUIRED = "login_2fa_required"
    LOGIN_2FA_SUCCESS = "login_2fa_success"
    LOGIN_2FA_FAILURE = "login_2fa_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REVOKED = "token_revoked"

    # Registration
    REGISTER_SUCCESS = "register_success"
    REGISTER_BLOCKED = "register_blocked"

    # Authorization
    PERMISSION_DENIED = "permission_denied"
    ADMIN_ACTION = "admin_action"

    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    QUOTA_EXCEEDED = "quota_exceeded"

    # IP Protection
    IP_BANNED = "ip_banned"
    IP_UNBANNED = "ip_unbanned"
    IP_BLOCKED = "ip_blocked"

    # File Security
    FILE_UPLOAD_SUCCESS = "file_upload_success"
    FILE_UPLOAD_BLOCKED = "file_upload_blocked"
    MALWARE_DETECTED = "malware_detected"

    # API Security
    CIRCUIT_BREAKER_TRIPPED = "circuit_breaker_tripped"
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"

    # Suspicious Activity
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    BRUTE_FORCE_DETECTED = "brute_force_detected"
    ANOMALY_DETECTED = "anomaly_detected"


# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Get security logger
security_logger = structlog.get_logger("security")

# Also set up standard logging for security events
_file_handler = None


def setup_security_log_file(log_path: str = "/var/log/instantrisk/security.log"):
    """
    Set up file-based security logging.

    Args:
        log_path: Path to security log file
    """
    global _file_handler

    try:
        import os
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        _file_handler = logging.FileHandler(log_path)
        _file_handler.setLevel(logging.INFO)
        _file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )

        # Add to security logger
        logging.getLogger("security").addHandler(_file_handler)

    except Exception as e:
        logging.warning(f"Could not set up security log file: {e}")


async def log_security_event(
    event_type: SecurityEventType,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    severity: str = "info"
) -> None:
    """
    Log a security event.

    Args:
        event_type: Type of security event
        user_id: User ID if applicable
        ip_address: Client IP address
        user_agent: Client user agent string
        details: Additional event details
        severity: Log severity (info, warning, error, critical)
    """
    event_data = {
        "event_type": event_type.value,
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        **(details or {})
    }

    # Log with appropriate severity
    log_func = getattr(security_logger, severity, security_logger.info)
    log_func(event_type.value, **event_data)

    # Also log to standard logger for file output
    standard_logger = logging.getLogger("security")
    log_message = json.dumps(event_data)

    if severity == "critical":
        standard_logger.critical(log_message)
    elif severity == "error":
        standard_logger.error(log_message)
    elif severity == "warning":
        standard_logger.warning(log_message)
    else:
        standard_logger.info(log_message)


# Convenience functions for common events

async def log_login_success(user_id: str, ip: str, user_agent: str = None):
    """Log successful login."""
    await log_security_event(
        SecurityEventType.LOGIN_SUCCESS,
        user_id=user_id,
        ip_address=ip,
        user_agent=user_agent
    )


async def log_login_failure(email: str, ip: str, reason: str = None, user_agent: str = None):
    """Log failed login attempt."""
    await log_security_event(
        SecurityEventType.LOGIN_FAILURE,
        ip_address=ip,
        user_agent=user_agent,
        details={"email": email, "reason": reason},
        severity="warning"
    )


async def log_rate_limit_exceeded(ip: str, endpoint: str, limit: str):
    """Log rate limit exceeded."""
    await log_security_event(
        SecurityEventType.RATE_LIMIT_EXCEEDED,
        ip_address=ip,
        details={"endpoint": endpoint, "limit": limit},
        severity="warning"
    )


async def log_ip_banned(ip: str, reason: str, duration_hours: int):
    """Log IP ban."""
    await log_security_event(
        SecurityEventType.IP_BANNED,
        ip_address=ip,
        details={"reason": reason, "duration_hours": duration_hours},
        severity="warning"
    )


async def log_file_blocked(filename: str, reason: str, ip: str, user_id: str = None):
    """Log blocked file upload."""
    await log_security_event(
        SecurityEventType.FILE_UPLOAD_BLOCKED,
        user_id=user_id,
        ip_address=ip,
        details={"filename": filename, "reason": reason},
        severity="warning"
    )


async def log_malware_detected(filename: str, threat: str, ip: str, user_id: str = None):
    """Log malware detection."""
    await log_security_event(
        SecurityEventType.MALWARE_DETECTED,
        user_id=user_id,
        ip_address=ip,
        details={"filename": filename, "threat": threat},
        severity="critical"
    )


async def log_suspicious_activity(ip: str, activity: str, details: Dict = None, user_id: str = None):
    """Log suspicious activity."""
    await log_security_event(
        SecurityEventType.SUSPICIOUS_ACTIVITY,
        user_id=user_id,
        ip_address=ip,
        details={"activity": activity, **(details or {})},
        severity="warning"
    )


async def log_circuit_breaker_tripped(category: str, reason: str):
    """Log circuit breaker trip."""
    await log_security_event(
        SecurityEventType.CIRCUIT_BREAKER_TRIPPED,
        details={"category": category, "reason": reason},
        severity="critical"
    )
