"""
InstantRisk V2 - Underwriter Copilot Router

Real-time AI guidance for underwriters during risk assessments.
Maintains per-session conversation memory with LangChain agents.

Routes:
    POST /api/v1/copilot/sessions                 - Create copilot session
    GET  /api/v1/copilot/sessions                 - List user's sessions
    GET  /api/v1/copilot/sessions/{id}            - Get session details
    DELETE /api/v1/copilot/sessions/{id}          - Close session
    POST /api/v1/copilot/sessions/{id}/ask        - Ask copilot a question
    GET  /api/v1/copilot/sessions/{id}/history    - Get conversation history
    GET  /api/v1/copilot/assessments/{id}/checklist - Pre-submission checklist
    GET  /api/v1/copilot/assessments/{id}/pricing  - Pricing analysis
"""

import logging
import uuid
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.services.copilot_service import get_copilot_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Schemas
# ============================================================

class SessionCreateRequest(BaseModel):
    """Request to create a copilot session."""
    assessment_id: str = Field(..., description="Assessment UUID to attach session to")
    risk_category: Optional[str] = Field(
        default="property",
        description="Risk category: property | cyber | marine | liability | financial_lines",
    )


class SessionResponse(BaseModel):
    """Copilot session details."""
    session_id: str
    assessment_id: str
    risk_category: str
    message_count: int
    created_at: str
    last_active: str
    ai_capabilities: List[str]


class AskRequest(BaseModel):
    """Request to ask the copilot."""
    message: str = Field(..., min_length=1, max_length=2000, description="Question or request for the copilot")
    include_assessment_snapshot: bool = Field(
        default=True,
        description="Refresh assessment data from DB before answering",
    )


class AskResponse(BaseModel):
    """Copilot answer."""
    session_id: str
    message_count: int
    answer: str
    suggestions: List[Dict[str, Any]]
    quick_actions: List[Dict[str, str]]
    ai_backend: str
    assessment_id: str


class MessageItem(BaseModel):
    """Single conversation message."""
    role: str
    content: str


# ============================================================
# Helpers
# ============================================================

async def _get_assessment_snapshot(
    assessment_id: str, db: AsyncSession
) -> Optional[Dict[str, Any]]:
    """Load assessment data from DB as dict."""
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        return None

    return {
        "id": str(assessment.id),
        "title": assessment.title,
        "risk_category": assessment.risk_category,
        "status": assessment.status,
        "decision": assessment.decision,
        "risk_score": assessment.risk_score,
        "confidence_score": assessment.confidence_score,
        "insured_name": assessment.insured_name,
        "sum_insured": assessment.sum_insured,
        "premium": assessment.premium,
        "deductible": assessment.deductible,
        "territory": assessment.territory,
        "inception_date": str(assessment.inception_date) if assessment.inception_date else None,
        "expiry_date": str(assessment.expiry_date) if assessment.expiry_date else None,
        "underwriter_notes": assessment.underwriter_notes,
        "ai_analysis": assessment.ai_analysis,
        "broker_name": getattr(assessment, "broker_name", None),
        "regulatory_framework": getattr(assessment, "regulatory_framework", None),
    }


# ============================================================
# Endpoints
# ============================================================

@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new copilot session",
)
async def create_session(
    req: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new AI copilot session for an assessment.

    Each session maintains its own conversation memory - the AI remembers
    what you discussed earlier in the session. Sessions expire after 8 hours
    of inactivity.

    The copilot is pre-loaded with the assessment context (risk score, sum insured,
    territory, etc.) so you don't need to re-explain the risk.
    """
    # Validate assessment access
    result = await db.execute(
        select(Assessment).where(Assessment.id == req.assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {req.assessment_id} not found",
        )

    # Load initial context
    assessment_data = await _get_assessment_snapshot(req.assessment_id, db)

    svc = get_copilot_service()
    session_id = f"copilot-{uuid.uuid4().hex[:12]}"

    session = svc.create_session(
        session_id=session_id,
        assessment_id=req.assessment_id,
        user_id=str(current_user.id),
        risk_category=req.risk_category or assessment.risk_category or "property",
        assessment_data=assessment_data,
    )

    capabilities = ["pricing_guidance", "clause_recommendation", "risk_analysis", "compliance_check"]
    if svc._langchain_available:
        capabilities.append("langchain_memory")
    if svc._bedrock_available:
        capabilities.append("bedrock_claude")

    return SessionResponse(
        session_id=session.session_id,
        assessment_id=session.assessment_id,
        risk_category=session.risk_category,
        message_count=session.message_count,
        created_at=session.created_at,
        last_active=session.last_active,
        ai_capabilities=capabilities,
    )


@router.get(
    "/sessions",
    summary="List your active copilot sessions",
)
async def list_sessions(
    current_user: User = Depends(get_current_user),
):
    """Lists all active copilot sessions for the current underwriter."""
    svc = get_copilot_service()
    sessions = svc.list_sessions(str(current_user.id))
    return {"sessions": sessions, "count": len(sessions)}


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Get copilot session details",
)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Returns details of an existing copilot session."""
    svc = get_copilot_service()
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    capabilities = ["pricing_guidance", "clause_recommendation", "risk_analysis", "compliance_check"]
    if svc._langchain_available:
        capabilities.append("langchain_memory")
    if svc._bedrock_available:
        capabilities.append("bedrock_claude")

    return SessionResponse(
        session_id=session.session_id,
        assessment_id=session.assessment_id,
        risk_category=session.risk_category,
        message_count=session.message_count,
        created_at=session.created_at,
        last_active=session.last_active,
        ai_capabilities=capabilities,
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Close a copilot session",
)
async def close_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Closes and removes a copilot session, freeing its memory."""
    svc = get_copilot_service()
    session = svc.get_session(session_id)
    if session and session.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    svc.close_session(session_id)


@router.post(
    "/sessions/{session_id}/ask",
    response_model=AskResponse,
    summary="Ask the underwriter copilot",
)
async def ask_copilot(
    session_id: str,
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ask the AI copilot a question in the context of your assessment.

    The copilot remembers previous messages in this session and maintains
    full assessment context. Example questions:

    - "What premium should I charge for this cyber risk?"
    - "What exclusions should I add given the poor loss history?"
    - "Is the current sum insured adequate for this property?"
    - "What Lloyd's compliance checks do I need to complete?"
    - "Flag any issues with this submission before I bind"
    """
    svc = get_copilot_service()
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Refresh assessment data if requested
    assessment_data = None
    if req.include_assessment_snapshot:
        assessment_data = await _get_assessment_snapshot(session.assessment_id, db)

    try:
        result = await svc.ask(
            session_id=session_id,
            message=req.message,
            assessment_data=assessment_data,
        )
        return AskResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Copilot ask error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Copilot error: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/history",
    summary="Get conversation history for a session",
)
async def get_session_history(
    session_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """Returns the full conversation history for a copilot session."""
    svc = get_copilot_service()
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.user_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    messages = session.messages[-limit:]
    return {
        "session_id": session_id,
        "assessment_id": session.assessment_id,
        "message_count": session.message_count,
        "messages": messages,
        "created_at": session.created_at,
        "last_active": session.last_active,
    }


@router.get(
    "/assessments/{assessment_id}/checklist",
    summary="Generate pre-submission underwriting checklist",
)
async def get_submission_checklist(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates a personalised pre-submission checklist based on the assessment's
    risk category, score, territory and other attributes.

    Items are prioritised as critical | high | medium.
    Returns overall completion percentage and whether the risk is ready to bind.
    """
    assessment_data = await _get_assessment_snapshot(assessment_id, db)
    if not assessment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found",
        )

    svc = get_copilot_service()
    return await svc.get_pre_submission_checklist(assessment_data)


@router.get(
    "/assessments/{assessment_id}/pricing",
    summary="Generate pricing analysis and market comparison",
)
async def get_pricing_analysis(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates detailed pricing analysis for an assessment.

    Returns:
    - Current rate-on-line percentage
    - Market rate range for the risk category
    - Suggested premium with loading rationale
    - Market adequacy rating (BELOW_MARKET | AT_MARKET | ABOVE_MARKET)
    - Key rating factors and applicable clauses
    """
    assessment_data = await _get_assessment_snapshot(assessment_id, db)
    if not assessment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found",
        )

    svc = get_copilot_service()
    return await svc.get_pricing_analysis(assessment_data)


@router.post(
    "/cleanup",
    summary="Clean up expired copilot sessions",
    include_in_schema=False,  # Admin endpoint
)
async def cleanup_sessions(
    max_age_hours: int = 8,
    current_user: User = Depends(get_current_user),
):
    """Remove copilot sessions older than max_age_hours (admin utility)."""
    svc = get_copilot_service()
    removed = svc.cleanup_old_sessions(max_age_hours=max_age_hours)
    return {"removed_sessions": removed, "max_age_hours": max_age_hours}
