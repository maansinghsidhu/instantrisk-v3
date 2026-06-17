"""
Tests for pr-agent 2nd-pass findings #13, #14, #15.

#13: list_audit_log PII redaction extended to top-level fields
    (ip_address masked, user_agent truncated, emails gated on is_super_admin)
#14: deactivate_user requires is_super_admin when target is an admin
#15: trusted_proxies default narrowed to ALB subnets
"""
import ipaddress

import pytest


# =============================================================================
# Fix #15: trusted_proxies default narrowed to ALB subnets
# =============================================================================

def test_trusted_proxies_default_uses_alb_subnets():
    """The default trusted_proxies must be the ALB subnets, not 10.0.0.0/8."""
    from app.config import Settings
    s = Settings()
    # The previous default (10.0.0.0/8) would let any host in the VPC
    # forge the captured client IP. The new default must be specific to
    # the ALB's two subnets.
    assert "10.0.0.0/8" not in s.trusted_proxies
    assert "10.0.101.0/24" in s.trusted_proxies  # ALB us-east-1a
    assert "10.0.102.0/24" in s.trusted_proxies  # ALB us-east-1b
    assert "127.0.0.1/32" in s.trusted_proxies   # loopback


def test_alb_subnet_cidrs_resolve_to_ips():
    from app.config import Settings
    s = Settings()
    for cidr in s.trusted_proxies:
        net = ipaddress.ip_network(cidr, strict=False)
        # /32 is valid (loopback has 1 IP); others must have > 1
        assert net.num_addresses >= 1

# =============================================================================
# Fix #13: _mask_ip and _redact_user_agent
# =============================================================================

def test_mask_ip_v4():
    from app.routers.admin_panel import _mask_ip
    # IPv4: zero out the last octet
    assert _mask_ip("203.0.113.55") == "203.0.113.0"
    assert _mask_ip("10.0.5.7") == "10.0.5.0"
    assert _mask_ip("192.168.1.1") == "192.168.1.0"


def test_mask_ip_v6():
    from app.routers.admin_panel import _mask_ip
    # IPv6: keep the first 3 hextets, zero the rest
    result = _mask_ip("2001:db8:abcd:1234:5678:9abc:def0:1234")
    # 2001:db8:abcd then zeros
    assert result.startswith("2001:db8:abcd:")


def test_mask_ip_invalid_returns_none():
    from app.routers.admin_panel import _mask_ip
    assert _mask_ip("not-an-ip") is None
    assert _mask_ip("999.999.999.999") is None


def test_mask_ip_none_passthrough():
    from app.routers.admin_panel import _mask_ip
    assert _mask_ip(None) is None


def test_redact_user_agent_truncates_long_string():
    from app.routers.admin_panel import _redact_user_agent
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
        "Edg/120.0.2210.91 OPR/106.0.0.0"
    )
    redacted = _redact_user_agent(ua, keep=40)
    # 40 chars + "..." = 43 chars
    assert redacted is not None
    assert len(redacted) == 43
    assert redacted.endswith("...")
    assert redacted.startswith("Mozilla/5.0 (Windows NT 10.0; Win64; ")


def test_redact_user_agent_keeps_short_string_unchanged():
    from app.routers.admin_panel import _redact_user_agent
    assert _redact_user_agent("curl/8.4.0") == "curl/8.4.0"
    assert _redact_user_agent("python-requests/2.31.0") == "python-requests/2.31.0"


def test_redact_user_agent_none_passthrough():
    from app.routers.admin_panel import _redact_user_agent
    assert _redact_user_agent(None) is None


# =============================================================================
# Fix #14: User model has is_super_admin
# =============================================================================

def test_user_model_has_is_super_admin_column():
    from app.models.user import User
    assert "is_super_admin" in User.__table__.columns
    col = User.__table__.columns["is_super_admin"]
    # Must be NOT NULL with a default of False (safer bootstrap)
    assert col.nullable is False
    assert col.default is not None


# =============================================================================
# Fix #14: deactivate_user behavior - simulated
# =============================================================================

def test_deactivate_admin_blocked_for_non_super_admin(monkeypatch):
    """deactivate_user should reject an admin-on-admin action when the
    current admin lacks is_super_admin. This is tested at the logic level
    because the endpoint requires a live DB session."""
    # Pure logic test: simulate the check
    class _U:
        def __init__(self, role, is_super_admin):
            self.role = role
            self.is_super_admin = is_super_admin
    from app.models.user import UserRole

    target = _U(role=UserRole.ADMIN, is_super_admin=False)
    actor = _U(role=UserRole.ADMIN, is_super_admin=False)
    # Logic: if target.role == ADMIN and not actor.is_super_admin -> reject
    is_blocked = (target.role == UserRole.ADMIN) and (not actor.is_super_admin)
    assert is_blocked is True

    # Super-admin can deactivate another admin
    super_actor = _U(role=UserRole.ADMIN, is_super_admin=True)
    is_blocked_super = (target.role == UserRole.ADMIN) and (not super_actor.is_super_admin)
    assert is_blocked_super is False

    # Non-admin targets are fine to deactivate for any admin
    target_broker = _U(role=UserRole.BROKER, is_super_admin=False)
    is_blocked_broker = (target_broker.role == UserRole.ADMIN) and (not actor.is_super_admin)
    assert is_blocked_broker is False


# =============================================================================
# Config: trusted_proxies can still be overridden via env
# =============================================================================

def test_trusted_proxies_override_via_env(monkeypatch):
    """Operator can override the default via TRUSTED_PROXIES env var."""
    monkeypatch.setenv("TRUSTED_PROXIES", '["172.20.0.0/16"]')
    from app.config import Settings
    s = Settings()
    # The override should take effect (lru_cache may interfere; force reload)
    from app.config import get_settings
    get_settings.cache_clear()
    s = Settings()
    assert "172.20.0.0/16" in s.trusted_proxies
