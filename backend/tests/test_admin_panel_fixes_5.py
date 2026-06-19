"""
Regression tests for the pr-agent 10th-pass findings against
admin_panel.py. Each test pins one of the bugs from the review:

- #1: get_user_usage NameError (Assessment/GeneratedDocument not imported)
- #2: reactivate_user body.reason NameError
- #3: list_audit_log NameError + shared-state bug (e referenced
       before the comprehension, plus masked_ip/redacted_ua hoisted
       above the loop so every entry shared the last entry's values)
- #4: _check_rate_limit runs AFTER state mutation, not before
- #5: _mask_ip IPv6 produces 9 hextets instead of 8
- #6: dead code (mrr = 0 twice in billing_summary)
- #7: misleading comment on User.token_invalidated_at column
- #8: deactivate_user audit log omits user_id (only email)
"""
import inspect

import pytest


# =============================================================================
# Fix #1: get_user_usage imports
# =============================================================================


def test_get_user_usage_imports_assessment_and_generated_document():
    """pr-agent 10th pass: get_user_usage referenced Assessment and
    GeneratedDocument but only the in-function imports existed. The
    endpoint raised NameError on every call. Both names must be
    importable from the module level."""
    import app.routers.admin_panel as mod

    src = inspect.getsource(mod)
    # The names must appear in the top-level import block (everything
    # before the first top-level function definition).
    import_line = src.find("import ipaddress")
    fn_line = src.find("\ndef _trusted_proxy_networks")
    top_block = (
        src[import_line:fn_line]
        if import_line >= 0 and fn_line > 0
        else src[:2000]
    )
    assert "from app.models.assessment import Assessment" in top_block, (
        "Assessment must be a top-level import so get_user_usage can "
        "reference it without a NameError at runtime."
    )
    assert "from app.models.generated_document import GeneratedDocument" in top_block, (
        "GeneratedDocument must be a top-level import so the same "
        "endpoint can count lifetime documents via the Assessment join."
    )
    # No in-function import should remain in get_user_usage.
    fn = inspect.getsource(mod.get_user_usage)
    assert "from app.models.assessment import Assessment" not in fn
    assert "from app.models.generated_document import GeneratedDocument" not in fn


# =============================================================================
# Fix #2: reactivate_user body.reason NameError
# =============================================================================


def test_reactivate_user_source_has_no_body_identifier():
    """pr-agent 10th pass: reactivate_user takes no request body but
    the patch_write_audit_log call referenced body.reason. The
    previous fix #25 patched _write_audit but missed patch_write_audit_log."""
    import app.routers.admin_panel as mod

    src = inspect.getsource(mod.reactivate_user)
    # The endpoint signature has no `body` parameter; any reference
    # like `body.reason` or `body.subscription_tier` is a NameError at
    # runtime. (Substring "body" appearing in a docstring or comment
    # is fine — only the identifier usage matters.)
    assert "body." not in src, (
        "reactivate_user must not reference `body.<x>` since its "
        "signature has no body parameter — that's a NameError at "
        "runtime. The previous fix #25 patched _write_audit but "
        "missed patch_write_audit_log."
    )
    assert '"reason": None' in src


# =============================================================================
# Fix #3: list_audit_log comprehension scoping
# =============================================================================


def test_list_audit_log_masks_inside_comprehension():
    """pr-agent 10th pass: masked_ip/redacted_ua were assigned once
    before the list comprehension (referencing `e` before it existed,
    AND every entry would have shared the last entry's values). Now
    the masking happens inside the per-entry construction."""
    import app.routers.admin_panel as mod

    src = inspect.getsource(mod.list_audit_log)
    # The comprehension must call _mask_ip and _redact_user_agent inside
    # the AdminAuditLogEntry constructor.
    entry_block = src.split("AdminAuditLogEntry(", 1)[1].split(
        "for e in entries", 1
    )[0]
    assert "_mask_ip(e.ip_address)" in entry_block
    assert "_redact_user_agent(e.user_agent)" in entry_block
    # And the old hoisted assignment must be gone.
    assert "masked_ip = _mask_ip(e.ip_address)" not in src
    assert "redacted_ua = _redact_user_agent(e.user_agent)" not in src


# =============================================================================
# Fix #4: rate limit runs BEFORE state mutation
# =============================================================================


@pytest.mark.parametrize(
    "fn_name",
    [
        "approve_user",
        "reject_user",
        "change_tier",
        "deactivate_user",
        "reactivate_user",
    ],
)
def test_rate_limit_runs_before_state_mutation(fn_name):
    """pr-agent 10th pass: every mutating admin endpoint called
    _check_rate_limit AFTER the user/subscription mutation block.
    The original "Fix #24" comment claimed the check ran before the
    mutation; it lied. Confirm the check now precedes every state
    mutation in the handler."""
    import app.routers.admin_panel as mod

    fn = getattr(mod, fn_name)
    src = inspect.getsource(fn)
    rate_limit_pos = src.find("_check_rate_limit(current_user.id)")
    assert rate_limit_pos > 0, (
        f"{fn_name} no longer calls _check_rate_limit"
    )

    # The rate limit MUST come before every state mutation in the
    # handler. Find the first occurrence of each mutation marker and
    # assert the rate-limit position precedes it.
    state_markers = [
        "user.approval_status =",
        "user.is_active =",
        "user.rejection_reason =",
        "user.approved_by =",
        "sub.tier =",
        "user.token_invalidated_at =",
    ]
    for marker in state_markers:
        idx = src.find(marker)
        if idx > 0:
            assert rate_limit_pos < idx, (
                f"{fn_name} has `{marker}` BEFORE `_check_rate_limit`. "
                f"Rate limit must precede any state mutation so a "
                f"rate-limited admin cannot change platform state."
            )


# =============================================================================
# Fix #5: _mask_ip IPv6 produces valid 8-hextet address
# =============================================================================


def test_mask_ip_ipv6_produces_8_hextets():
    """pr-agent 10th pass: the previous IPv6 mask appended 6 zero
    hextets after the first 3 hextets, producing 9 hextets total —
    an invalid IPv6 address. Fix: append only 5 zeros (3+5=8)."""
    import ipaddress

    from app.routers.admin_panel import _mask_ip

    result = _mask_ip("2001:db8:abcd:1234:5678:9abc:def0:1234")
    assert result is not None
    parsed = ipaddress.ip_address(result)
    assert isinstance(parsed, ipaddress.IPv6Address)
    # Address must have exactly 8 hextets.
    assert result.count(":") == 7, (
        f"IPv6 must have exactly 8 hextets (7 colons); got {result!r}"
    )
    # /48 prefix preserved.
    assert result.startswith("2001:db8:abcd:")


def test_mask_ip_ipv4_unchanged():
    """Sanity: the IPv4 path is not affected by the IPv6 fix."""
    from app.routers.admin_panel import _mask_ip

    assert _mask_ip("203.0.113.55") == "203.0.113.0"


# =============================================================================
# Fix #6: dead `mrr = 0` removed
# =============================================================================


def test_billing_summary_does_not_set_mrr_twice():
    """pr-agent 10th pass: `mrr = 0` was assigned twice in
    billing_summary. Confirm only one assignment remains."""
    import app.routers.admin_panel as mod

    src = inspect.getsource(mod.billing_summary)
    assert src.count("mrr = 0") == 1, (
        f"billing_summary assigns mrr = 0 exactly once; got "
        f"{src.count('mrr = 0')} occurrences."
    )


# =============================================================================
# Fix #7: misleading token_invalidated_at comment removed
# =============================================================================


def test_user_token_invalidated_at_doc_is_accurate():
    """pr-agent 10th pass: the column comment claimed the
    reactivation flow clears token_invalidated_at, but the actual
    reactivation code deliberately DOES NOT clear it (monotonic
    high-water mark). The fix documents the actual behavior."""
    from app.models.user import User

    col = User.__table__.columns["token_invalidated_at"]
    comment = (col.comment or "").lower()
    assert (
        "monotonic" in comment
        or "never cleared" in comment
        or "high-water" in comment
    ), (
        f"token_invalidated_at column comment must describe the "
        f"monotonic high-water-mark behavior, not the misleading "
        f"'reactivation clears it' claim. Got: {col.comment!r}"
    )


# =============================================================================
# Fix #8: deactivate_user audit log includes user_id
# =============================================================================


def test_deactivate_user_audit_log_includes_user_id():
    """pr-agent 10th pass: every other mutating endpoint passed
    user_id=current_user.id to patch_write_audit_log; deactivate
    omitted it, leaving user_id=None in the regulatory chain row.
    Now all calls are aligned."""
    import app.routers.admin_panel as mod

    src = inspect.getsource(mod.deactivate_user)
    # Find the patch_write_audit_log block.
    block = src.split("patch_write_audit_log(", 1)[1]
    block = block.split(")", 1)[0]
    assert "user_id=current_user.id" in block, (
        "deactivate_user must pass user_id=current_user.id to "
        "patch_write_audit_log, matching approve_user, reject_user, "
        "change_tier, and reactivate_user."
    )
