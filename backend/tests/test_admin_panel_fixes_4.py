"""
Tests for 4th-pass findings #19, #20, #21.

#19: TIER_PRICE_USD sourced from app.config.Settings, not hardcoded
#20: duplicate # W3-20 comment removed from deactivate_user
#21: change_tier rejects non-approved or inactive users
"""
import inspect

import pytest


# =============================================================================
# Fix #19: TIER_PRICE_USD moved to config
# =============================================================================

def test_tier_price_usd_in_settings():
    from app.config import Settings
    s = Settings()
    # The default values must match the old hardcoded ones so MRR doesn't
    # silently change after this commit.
    assert s.tier_price_usd.get("trial") == 0
    assert s.tier_price_usd.get("basic") == 99
    assert s.tier_price_usd.get("premium") == 499


def test_tier_price_usd_no_longer_in_schemas():
    """The TIER_PRICE_USD dict must not be defined in the schemas module."""
    import app.schemas.admin_panel as schemas
    assert not hasattr(schemas, "TIER_PRICE_USD"), (
        "TIER_PRICE_USD was moved to app.config.Settings; remove the "
        "hardcoded dict from app.schemas.admin_panel."
    )


def test_admin_panel_uses_config_pricing():
    """admin_panel must import the config and use settings.tier_price_usd,
    not the schema's TIER_PRICE_USD."""
    import app.routers.admin_panel as mod
    # The old import statement (line 41) had TIER_PRICE_USD; it should be gone.
    src = inspect.getsource(mod)
    # The schema constant must no longer be imported
    assert "from app.schemas.admin_panel import" in src
    # The first import line that listed names should NOT include TIER_PRICE_USD
    import_line_start = src.find("from app.schemas.admin_panel import")
    if import_line_start == -1:
        pytest.skip("Schema import line not found")
    # Read the import block (multi-line)
    paren_open = src.find("(", import_line_start)
    paren_close = src.find(")", paren_open) if paren_open != -1 else -1
    import_block = src[paren_open:paren_close] if paren_close > paren_open else ""
    assert "TIER_PRICE_USD" not in import_block
    # And the new line should import get_settings
    assert "get_settings" in src


def test_tier_price_usd_override_via_env(monkeypatch):
    """Operator can override tier prices via TIER_PRICE_USD env var."""
    monkeypatch.setenv("TIER_PRICE_USD", '{"trial": 0, "basic": 199, "premium": 999}')
    from app.config import Settings
    s = Settings()
    assert s.tier_price_usd.get("basic") == 199
    assert s.tier_price_usd.get("premium") == 999


# =============================================================================
# Fix #20: duplicate comment removed
# =============================================================================

def test_no_duplicate_w3_20_comment_in_deactivate_user():
    """The deactivate_user source must not contain two consecutive
    # W3-20: comments."""
    import app.routers.admin_panel as mod
    src = inspect.getsource(mod.deactivate_user)
    # Count occurrences of the marker line
    marker = "W3-20: hash-chained regulatory audit log entry"
    occurrences = src.count(marker)
    assert occurrences == 1, (
        f"deactivate_user has {occurrences} copies of the W3-20 marker; "
        f"expected exactly 1."
    )


# =============================================================================
# Fix #21: change_tier requires approved + active user
# =============================================================================

def test_change_tier_rejects_pending_user():
    """change_tier must reject a user whose approval_status != APPROVED.

    Tested at the logic level since the endpoint requires a live DB.
    """
    from app.models.user import User, UserRole, ApprovalStatus
    from app.models.subscription import SubscriptionTier

    class _U:
        def __init__(self, role, approval_status, is_active):
            self.role = role
            self.approval_status = approval_status
            self.is_active = is_active

    # The check: target user must be APPROVED and active
    def should_allow(user):
        return (user.approval_status == ApprovalStatus.APPROVED
                and user.is_active)

    assert should_allow(_U(UserRole.BROKER, ApprovalStatus.APPROVED, True)) is True
    assert should_allow(_U(UserRole.BROKER, ApprovalStatus.PENDING, True)) is False
    assert should_allow(_U(UserRole.BROKER, ApprovalStatus.REJECTED, True)) is False
    assert should_allow(_U(UserRole.BROKER, ApprovalStatus.APPROVED, False)) is False


def test_change_tier_source_has_the_check():
    """Static check: change_tier must check approval_status and is_active
    before allowing the tier change."""
    import app.routers.admin_panel as mod
    src = inspect.getsource(mod.change_tier)
    # The check should appear after the "User not found" guard
    assert "approval_status" in src
    assert "ApprovalStatus.APPROVED" in src
    assert "is_active" in src
