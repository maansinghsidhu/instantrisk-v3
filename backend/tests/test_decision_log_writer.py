"""
Tests for the W3-19/W3-20 decision log writer.

Verifies:
- write_ai_decision_log persists a row with the chain columns populated
- write_audit_log persists a row with the chain columns populated
- verify_chain() detects a tampered row
- Genesis row's prev_hash is the all-zeros sentinel
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone


@pytest.fixture
def db_session():
    """In-memory mock session. The writer uses .add, .commit, .refresh,
    and .execute (with .scalar_one_or_none on the result)."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "_refreshed", True))

    written: list = []

    async def fake_execute(stmt):
        result = MagicMock()
        # The writer uses scalar_one_or_none() to fetch the latest row.
        # verify_chain uses scalars().all() to walk the entire chain.
        result.scalar_one_or_none = lambda: (written[-1] if written else None)
        result.scalars = MagicMock(
            return_value=MagicMock(all=lambda: list(written))
        )
        return result

    session.execute = fake_execute

    original_add = session.add

    def track(obj):
        written.append(obj)
        obj.id = len(written)
        obj.timestamp = datetime.now(timezone.utc)
        return original_add(obj)

    session.add = track
    session._written = written
    return session


def test_apply_revert():
    from app.patches import decision_log_writer
    state1 = decision_log_writer.apply()
    state2 = decision_log_writer.apply()
    state3 = decision_log_writer.revert()
    assert state1 == {"applied": True, "scope": "library"}
    assert state2 == {"applied": True, "scope": "library"}
    assert state3 == {"reverted": True}


@pytest.mark.asyncio
async def test_ai_decision_log_genesis_row(db_session):
    from app.patches.decision_log_writer import write_ai_decision_log, GENESIS_HASH

    row = await write_ai_decision_log(
        db_session,
        agent_name="underwriter",
        decision_type="go_no_go",
        input_data={"risk_score": 78},
        output_data={"decision": "GO"},
        confidence_score=0.86,
    )
    assert row.id == 1
    assert row.prev_hash == GENESIS_HASH
    assert row.input_hash != ""
    assert row.agent_name == "underwriter"
    assert row.decision_type == "go_no_go"


@pytest.mark.asyncio
async def test_ai_decision_log_chains(db_session):
    from app.patches.decision_log_writer import write_ai_decision_log, compute_row_hash

    r1 = await write_ai_decision_log(
        db_session, agent_name="a", decision_type="d1", input_data={"i": 1}
    )
    r2 = await write_ai_decision_log(
        db_session, agent_name="a", decision_type="d2", input_data={"i": 2}
    )
    r3 = await write_ai_decision_log(
        db_session, agent_name="a", decision_type="d3", input_data={"i": 3}
    )

    assert r2.prev_hash != r1.prev_hash
    expected_r2 = compute_row_hash(
        prev_hash=r1.prev_hash,
        prev_pk=r1.id,
        prev_ts=r1.timestamp,
        input_hash=r1.input_hash,
    )
    assert r2.prev_hash == expected_r2
    assert r3.prev_hash != r2.prev_hash
    assert r1.input_hash != r2.input_hash != r3.input_hash


@pytest.mark.asyncio
async def test_audit_log_genesis(db_session):
    from app.patches.decision_log_writer import write_audit_log, GENESIS_HASH

    row = await write_audit_log(
        db_session,
        action="user.approve",
        user_email="admin@example.com",
        entity_type="user",
        entity_id="u-1",
    )
    assert row.id == 1
    assert row.prev_hash == GENESIS_HASH
    assert row.input_hash != ""
    assert row.action == "user.approve"


@pytest.mark.asyncio
async def test_audit_log_chains(db_session):
    from app.patches.decision_log_writer import write_audit_log

    r1 = await write_audit_log(db_session, action="user.approve", entity_id="u-1")
    r2 = await write_audit_log(db_session, action="user.reject", entity_id="u-2")
    assert r1.prev_hash == "0" * 64
    assert r2.prev_hash != r1.prev_hash
    assert r1.input_hash != r2.input_hash


@pytest.mark.asyncio
async def test_compute_input_hash_deterministic():
    from app.patches.decision_log_writer import compute_input_hash
    h1 = compute_input_hash({"a": 1, "b": 2})
    h2 = compute_input_hash({"b": 2, "a": 1})
    assert h1 == h2


@pytest.mark.asyncio
async def test_compute_input_hash_distinct_for_different_data():
    from app.patches.decision_log_writer import compute_input_hash
    assert compute_input_hash({"x": 1}) != compute_input_hash({"x": 2})


@pytest.mark.asyncio
async def test_verify_chain_intact_for_ai_decision_log(db_session):
    """verify_chain must accept a 3-row chain written by write_ai_decision_log.

    Regression test for the bug the PR-Agent review caught: the verifier
    used a different hash formula than the writer, so the chain was never
    actually verifiable.
    """
    from app.patches.decision_log_writer import (
        write_ai_decision_log,
        verify_chain,
    )

    class _MockAIDecisionLog:
        pass

    # Write 3 rows using the real writer against the mocked session.
    await write_ai_decision_log(
        db_session, agent_name="underwriter", decision_type="d1", input_data={"i": 1}
    )
    await write_ai_decision_log(
        db_session, agent_name="underwriter", decision_type="d2", input_data={"i": 2}
    )
    await write_ai_decision_log(
        db_session, agent_name="underwriter", decision_type="d3", input_data={"i": 3}
    )

    # For verify_chain, model needs an .id and .prev_hash attribute. The
    # writer's session mock stamped those onto the mock objects. So we
    # return the written list directly as the "model" type.
    ok, errors = await verify_chain(db_session, type(db_session._written[0]))
    assert ok is True, f"chain not valid: {errors}"
    assert errors == []


@pytest.mark.asyncio
async def test_verify_chain_intact_for_audit_log(db_session):
    from app.patches.decision_log_writer import write_audit_log, verify_chain

    await write_audit_log(db_session, action="user.approve", entity_id="u-1")
    await write_audit_log(db_session, action="user.reject", entity_id="u-2")

    ok, errors = await verify_chain(db_session, type(db_session._written[0]))
    assert ok is True, f"chain not valid: {errors}"
    assert errors == []


@pytest.mark.asyncio
async def test_verify_chain_detects_tampered_row(db_session):
    """If a row's prev_hash is altered, verify_chain must report a break."""
    from app.patches.decision_log_writer import write_audit_log, verify_chain

    await write_audit_log(db_session, action="user.approve", entity_id="u-1")
    await write_audit_log(db_session, action="user.reject", entity_id="u-2")
    # Tamper with the second row's prev_hash.
    db_session._written[1].prev_hash = "0" * 64
    ok, errors = await verify_chain(db_session, type(db_session._written[0]))
    assert ok is False
    assert len(errors) == 1
    assert "row[1]" in errors[0]
    assert "mismatch" in errors[0]
