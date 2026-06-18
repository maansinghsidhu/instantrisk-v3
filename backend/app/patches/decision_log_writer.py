"""
InstantRisk V3 - W3-19 patch: AIDecisionLog + AuditLog hash-chained writer.

This is the v3 adaptation of the audit's `patches/decision_log_writer.py`.
The original import path was `app.models.lloyds.AIDecisionLog`; v2-platform
has no `lloyds.py` (it was removed in migration 099). The models were
re-introduced in `app/models/decision_log.py` (migration 106).

Every call to `write_ai_decision_log` or `write_audit_log` chains the new
row to the previous row's hash. `verify_chain(db, model)` walks the chain
and reports the first tampered row, or returns `(True, [])` if intact.

Usage in agent code:
    from app.patches.decision_log_writer import write_ai_decision_log

    await write_ai_decision_log(
        db,
        agent_name="underwriter",
        decision_type="go_no_go",
        assessment_id=assessment.id,
        input_data={"risk_score": 78, "territory": "US"},
        output_data={"decision": "GO", "confidence": 0.86},
        confidence_score=0.86,
        reasoning="Strong risk score, clean loss history",
        key_factors=["risk_score_78", "no_losses_5y"],
    )

Verify the chain:
    from app.patches.decision_log_writer import verify_chain
    ok, errors = await verify_chain(db, AIDecisionLog)
    if not ok:
        log.error("ai_decision_log chain broken: %s", errors)
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Type

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("patches.decision_log_writer")

__all__ = [
    "GENESIS_HASH",
    "compute_input_hash",
    "compute_row_hash",
    "write_ai_decision_log",
    "write_audit_log",
    "verify_chain",
]


#: The "previous hash" value for the very first row in a chain. Chosen as
#: 64 zero hex digits to mirror the length of a SHA-256 digest.
GENESIS_HASH: str = "0" * 64


def _canonicalize(data: Any) -> str:
    try:
        return json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))
    except Exception:
        return repr(data)


def compute_input_hash(input_data: Any) -> str:
    return hashlib.sha256(_canonicalize(input_data).encode("utf-8")).hexdigest()


def compute_row_hash(prev_hash: str, prev_pk: Any, prev_ts: Any, input_hash: str) -> str:
    if isinstance(prev_ts, datetime):
        ts_str = prev_ts.isoformat()
    else:
        ts_str = str(prev_ts)
    payload = "|".join([prev_hash, str(prev_pk), ts_str, input_hash])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _latest_row(db: AsyncSession, model: Type[Any]) -> Optional[Any]:
    pk_col = getattr(model, "id", None)
    if pk_col is None:
        return None
    result = await db.execute(select(model).order_by(desc(pk_col)).limit(1))
    return result.scalar_one_or_none()


async def write_ai_decision_log(
    db: AsyncSession,
    agent_name: str,
    decision_type: str,
    *,
    agent_version: Optional[str] = None,
    model_name: Optional[str] = None,
    assessment_id: Optional[Any] = None,
    input_data: Optional[Dict[str, Any]] = None,
    output_data: Optional[Dict[str, Any]] = None,
    confidence_score: Optional[float] = None,
    reasoning: Optional[str] = None,
    key_factors: Optional[List[str]] = None,
    human_override: bool = False,
    override_by: Optional[Any] = None,
    override_reason: Optional[str] = None,
    override_at: Optional[datetime] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Any:
    """Persist a single AIDecisionLog row with a chained ``prev_hash``."""
    from app.models.decision_log import AIDecisionLog

    input_hash = compute_input_hash(input_data or {})
    prev = await _latest_row(db, AIDecisionLog)
    if prev is None:
        prev_hash = GENESIS_HASH
    else:
        prev_hash = compute_row_hash(
            prev_hash=prev.prev_hash or GENESIS_HASH,
            prev_pk=prev.id,
            prev_ts=prev.timestamp,
            input_hash=getattr(prev, "input_hash", "") or "",
        )

    row = AIDecisionLog(
        agent_name=agent_name,
        agent_version=agent_version,
        model_name=model_name,
        decision_type=decision_type,
        assessment_id=assessment_id,
        input_data=input_data or {},
        output_data=output_data or {},
        confidence_score=confidence_score,
        reasoning=reasoning,
        key_factors=key_factors or [],
        human_override=human_override,
        override_by=override_by,
        override_reason=override_reason,
        override_at=override_at,
        extra=extra or {},
    )
    setattr(row, "prev_hash", prev_hash)
    setattr(row, "input_hash", input_hash)

    db.add(row)
    # Fix #31 (8th pr-agent): the previous version called db.commit()
    # here which committed the caller's open transaction. That broke
    # atomicity: if a subsequent caller-side write failed, the
    # regulatory AuditLog row would already be persisted while the
    # user mutation was not. The helper now flushes only; the caller
    # owns the transaction boundary.
    await db.flush()
    await db.refresh(row)
    logger.info(
        "ai_decision_log row=%s agent=%s decision=%s prev_hash=%s..",
        row.id, agent_name, decision_type, prev_hash[:12],
    )
    return row


async def write_audit_log(
    db: AsyncSession,
    action: str,
    *,
    user_id: Optional[Any] = None,
    user_email: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Any:
    """Persist a single AuditLog row with a chained ``prev_hash``."""
    from app.models.decision_log import AuditLog

    payload = {
        "action": action,
        "user_id": str(user_id) if user_id else None,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "old_values": old_values or {},
        "new_values": new_values or {},
    }
    input_hash = compute_input_hash(payload)
    prev = await _latest_row(db, AuditLog)
    if prev is None:
        prev_hash = GENESIS_HASH
    else:
        prev_hash = compute_row_hash(
            prev_hash=prev.prev_hash or GENESIS_HASH,
            prev_pk=prev.id,
            prev_ts=prev.timestamp,
            input_hash=getattr(prev, "input_hash", "") or "",
        )

    row = AuditLog(
        user_id=user_id,
        user_email=user_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values or {},
        new_values=new_values or {},
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id,
    )
    setattr(row, "prev_hash", prev_hash)
    setattr(row, "input_hash", input_hash)

    db.add(row)
    # Fix #31 (8th pr-agent): see write_ai_decision_log. Use flush() so
    # the caller owns the transaction boundary.
    await db.flush()
    await db.refresh(row)
    logger.info(
        "audit_log row=%s action=%s prev_hash=%s..",
        row.id, action, prev_hash[:12],
    )
    return row


async def verify_chain(db: AsyncSession, model: Type[Any]) -> Tuple[bool, List[str]]:
    """Walk the entire log and verify that every ``prev_hash`` is correct.

    The verification rule mirrors the writer exactly: for each row at
    position i, ``rows[i].prev_hash`` must equal
    ``compute_row_hash(rows[i-1].prev_hash, rows[i-1].id,
    rows[i-1].timestamp, rows[i-1].input_hash)``. For the first row
    (i == 0), ``prev_hash`` must equal ``GENESIS_HASH``.

    Returns ``(True, [])`` if the chain is intact, otherwise
    ``(False, [error, ...])`` with the first-detected break.
    """
    result = await db.execute(select(model).order_by(model.id))
    rows = result.scalars().all()
    errors: List[str] = []
    if not rows:
        return True, errors
    # Row 0 must point at the genesis.
    first = rows[0]
    if (first.prev_hash or "") != GENESIS_HASH:
        errors.append(
            f"row[0] id={first.id} prev_hash mismatch: "
            f"expected GENESIS_HASH ({GENESIS_HASH[:12]}..) "
            f"got {(first.prev_hash or '')[:12]}.."
        )
        return False, errors
    for i in range(1, len(rows)):
        prev_row = rows[i - 1]
        cur_row = rows[i]
        # The writer stored cur_row.prev_hash as compute_row_hash(prev_row's metadata).
        expected = compute_row_hash(
            prev_hash=prev_row.prev_hash or GENESIS_HASH,
            prev_pk=prev_row.id,
            prev_ts=prev_row.timestamp,
            input_hash=getattr(prev_row, "input_hash", "") or "",
        )
        actual = cur_row.prev_hash or ""
        if actual != expected:
            errors.append(
                f"row[{i}] id={cur_row.id} prev_hash mismatch: "
                f"expected {expected[:12]}.. got {actual[:12]}.."
            )
            return False, errors
    return True, errors

# Fix #29 (7th pr-agent): removed the previous apply() / revert() stubs
# which were no-ops that toggled a private _APPLIED flag. They were not
# consumed anywhere in the codebase and just confused the runbook.
