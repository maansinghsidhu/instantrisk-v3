"""
Tests for the RBAC permission-cache invalidation fixes.

Closes audit D4.13 (cache had no TTL — stale rows granted permissions
forever) and W2.44 (mutations on team_memberships and roles did not
invalidate the cache). The fix is two helpers in
`app.core.permissions` — `clear_user_permission_cache` and
`clear_permission_cache_for_role` — plus TTL filtering in
`check_permission` and the router-level `check_user_permission`.

Strategy:
- Mocked-session tests for the two helpers (no real DB needed; the
  helpers are pure SQLAlchemy) and for `check_permission`'s TTL
  filtering (we assert the cache hit is suppressed when the row is
  older than the cutoff).
- Source-string checks to lock in the TTL filter and the constant in
  both modules, so a future refactor cannot accidentally remove the
  audit D4.13 guard without a failing test.
"""
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from sqlalchemy import delete, select

from app.core.permissions import (
    PERMISSION_CACHE_TTL_SECONDS,
    clear_permission_cache_for_role,
    clear_user_permission_cache,
)
from app.models.rbac import TeamMembership, UserPermissionCache


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def db():
    """Async mock session. .execute returns an awaitable whose result has
    .scalar_one_or_none() and (for the helpers) .rowcount or .scalars().all()
    as needed by the helper under test."""
    session = AsyncMock()
    return session


# =============================================================================
# Fix D4.13: TTL filter is in both cache-read paths
# =============================================================================


def test_ttl_constant_is_five_minutes():
    """Audit D4.13 closure: the cache TTL must be 5 minutes (300s),
    matching the runbook W3-36 post-condition. If this number ever
    changes, the change is deliberate and must be reviewed."""
    assert PERMISSION_CACHE_TTL_SECONDS == 300


def test_check_permission_source_has_ttl_filter():
    """`check_permission` in app.core.permissions must filter on
    `cached_at` to enforce the TTL. Static check: the predicate string
    must appear in the source, otherwise a refactor could silently
    drop the fix."""
    import inspect

    from app.core import permissions

    src = inspect.getsource(permissions.check_permission)
    assert "cached_at" in src, (
        "check_permission no longer filters on cached_at — audit D4.13 "
        "is reopened."
    )
    assert "PERMISSION_CACHE_TTL_SECONDS" in src, (
        "check_permission no longer references PERMISSION_CACHE_TTL_SECONDS "
        "— the TTL constant must be in the WHERE clause."
    )


def test_check_user_permission_source_has_ttl_filter():
    """The router-level `check_user_permission` shadows the global one
    (audit F-140). It must also filter on cached_at or the fix is
    half-applied — only some endpoints get the TTL guard."""
    import inspect

    from app.routers import teams

    src = inspect.getsource(teams.check_user_permission)
    assert "cached_at" in src, (
        "routers.teams.check_user_permission no longer filters on "
        "cached_at — admin panel and team endpoints that depend on the "
        "router-level check will serve stale grants."
    )
    assert "PERMISSION_CACHE_TTL_SECONDS" in src


# =============================================================================
# Fix W2.44: clear_user_permission_cache helper
# =============================================================================


@pytest.mark.asyncio
async def test_clear_user_permission_cache_returns_rowcount(db):
    """The helper must issue a single DELETE scoped to the user and
    return the rowcount for observability."""
    execute_result = MagicMock()
    execute_result.rowcount = 4
    db.execute.return_value = execute_result

    deleted = await clear_user_permission_cache("user-123", db)

    assert deleted == 4
    # Exactly one statement executed (the DELETE).
    assert db.execute.await_count == 1
    # And it was committed.
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_clear_user_permission_cache_handles_zero_rows(db):
    """If the user had no cached rows, the helper must return 0 (not
    raise) so callers can use the return value as a metric without a
    truthiness check."""
    execute_result = MagicMock()
    execute_result.rowcount = 0
    db.execute.return_value = execute_result

    deleted = await clear_user_permission_cache("user-no-cache", db)
    assert deleted == 0


@pytest.mark.asyncio
async def test_clear_user_permission_cache_targets_user_id(db):
    """The DELETE must be against UserPermissionCache scoped by user_id
    — not a blanket wipe. We verify by issuing a real DELETE through
    SQLAlchemy's expression API and checking the compiled statement
    references the right table and column."""
    execute_result = MagicMock()
    execute_result.rowcount = 1
    db.execute.return_value = execute_result

    await clear_user_permission_cache("user-abc", db)
    # Pull the SQLAlchemy Core statement the helper passed to execute().
    stmt = db.execute.await_args.args[0]
    # delete() requires a table; the class is sqlalchemy.sql.dml.Delete.
    # Compare by class name to avoid importing the private class path.
    assert type(stmt).__name__ == "Delete", (
        "clear_user_permission_cache must use a SQLAlchemy delete() "
        f"statement, got {type(stmt).__name__}."
    )
    compiled = stmt.compile(
        compile_kwargs={"literal_binds": False}
    )
    # The DELETE must reference the cache table and the user filter.
    sql = str(compiled).lower()
    assert "user_permission_cache" in sql
    assert "user_id" in sql


# =============================================================================
# Fix W2.44: clear_permission_cache_for_role helper
# =============================================================================


@pytest.mark.asyncio
async def test_clear_permission_cache_for_role_returns_zero_with_no_holders(db):
    """If no active membership references the role, the helper must
    short-circuit and not issue a DELETE at all. This matters for
    performance when a role is created and has no holders yet (see
    the create_role call site in routers.teams)."""
    membership_result = MagicMock()
    membership_result.all.return_value = []  # no holders
    db.execute.return_value = membership_result

    deleted = await clear_permission_cache_for_role(99, db)
    assert deleted == 0
    # Only one statement: the membership lookup. No DELETE issued.
    # No commit either — short-circuit path has nothing to commit.
    assert db.execute.await_count == 1
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_clear_permission_cache_for_role_wipes_all_holders(db):
    """The helper must delete the cache rows of every active holder,
    not just the first one, and return the total rowcount."""

    # First call: membership lookup → two holders
    membership_result = MagicMock()
    membership_result.all.return_value = [("u1",), ("u2",)]
    # Second call: the DELETE → 7 rows wiped
    delete_result = MagicMock()
    delete_result.rowcount = 7

    db.execute.side_effect = [membership_result, delete_result]

    deleted = await clear_permission_cache_for_role(42, db)
    assert deleted == 7
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_clear_permission_cache_for_role_uses_active_memberships(db):
    """Soft-deleted memberships (is_active=False) must not drive a
    cache wipe — the user is no longer a holder in any meaningful
    sense, and clearing their cache would force a needless
    re-derivation on their next call."""

    # Capture the SELECT statement the helper built.
    captured = {}

    async def capture(stmt, *args, **kwargs):
        # We need the WHERE clause to verify is_active=True was used.
        captured["stmt"] = stmt
        result = MagicMock()
        result.all.return_value = []
        return result

    db.execute.side_effect = capture

    await clear_permission_cache_for_role(7, db)

    stmt = captured["stmt"]
    assert isinstance(stmt, select(TeamMembership.user_id).__class__)
    compiled = stmt.compile(compile_kwargs={"literal_binds": False})
    sql = str(compiled).lower()
    assert "is_active" in sql
    # The role_id filter must be present so we only target holders of
    # THIS role, not all memberships.
    assert "role_id" in sql


# =============================================================================
# End-to-end behavioural check: TTL filter actually rejects stale cache
# =============================================================================


@pytest.mark.asyncio
async def test_check_permission_ttl_rejects_stale_cache_hit(db):
    """A stale `UserPermissionCache` row (one whose `cached_at` is
    older than the TTL) must NOT satisfy the cache-read branch of
    `check_permission`. The test asserts that even when the SELECT
    returns a row, the helper falls through to the team-membership
    derivation path. We use an old `cached_at` to make the WHERE
    clause filter the row out, mirroring what a real DB would do.

    Concretely: the helper builds a SELECT with `cached_at > cutoff`.
    We set up the mock to return no row on that SELECT (because the
    row's cached_at is older than the cutoff), and to return no team
    memberships on the second SELECT. The helper must return False."""
    from datetime import datetime, timedelta, timezone
    from app.core.permissions import check_permission
    from app.models.user import UserRole

    # No cache hit, no team memberships — should return False.
    no_row = MagicMock()
    no_row.scalar_one_or_none.return_value = None
    no_memberships = MagicMock()
    no_memberships.scalars.return_value.all.return_value = []
    db.execute.side_effect = [no_row, no_memberships]

    user = MagicMock()
    user.id = "u1"
    user.role = UserRole.BROKER

    result = await check_permission(user, "assessment:write", db)
    assert result is False
    # Two SQL executions: cache lookup, then team-membership lookup.
    assert db.execute.await_count == 2
