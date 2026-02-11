"""
InstantRisk V2 - Sharing Router

API endpoints for creating and managing temporary shareable links
to assessments. Links expire after 24 hours.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.feature_gate import require_feature
from app.models.user import User
from app.models.assessment import Assessment
from app.models.share_link import ShareLink


router = APIRouter(prefix="/share", tags=["Sharing"])


# =============================================================================
# Schemas
# =============================================================================

class ShareLinkCreate(BaseModel):
    """Request schema for creating a share link."""
    hours_valid: Optional[int] = 24  # Default 24 hours, max 48 hours


class ShareLinkResponse(BaseModel):
    """Response schema for share link details."""
    token: str
    share_url: str
    assessment_id: str
    expires_at: str
    is_valid: bool
    access_count: int

    class Config:
        from_attributes = True


class SharedAssessmentResponse(BaseModel):
    """Response schema for accessing a shared assessment."""
    assessment_id: str
    insured_name: Optional[str]
    risk_category: Optional[str]
    status: str
    decision: Optional[str]
    decision_rationale: Optional[str]
    risk_score: Optional[int]
    confidence_score: Optional[int]
    underwriting_percentage: Optional[float]
    premium_price: Optional[float]
    risk_analysis: Optional[dict]
    created_at: str
    shared_by: str
    expires_at: str


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/assessments/{assessment_id}", response_model=ShareLinkResponse)
async def create_share_link(
    assessment_id: str,
    request: ShareLinkCreate = ShareLinkCreate(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_feature("shareable_link"))
):
    """
    Create a temporary shareable link for an assessment.

    The link expires after 24 hours by default (max 48 hours).
    Anyone with the link can view the assessment results without logging in.
    """
    # Validate hours_valid (1-48 hours)
    hours_valid = min(max(request.hours_valid, 1), 48)

    # Check if assessment exists and belongs to user
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )

    # Check ownership (unless admin)
    if assessment.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only share your own assessments"
        )

    # Create share link
    share_link = ShareLink(
        assessment_id=assessment_id,
        created_by=current_user.id,
        expires_at=datetime.utcnow() + timedelta(hours=hours_valid)
    )
    db.add(share_link)
    await db.commit()
    await db.refresh(share_link)

    return ShareLinkResponse(
        token=share_link.token,
        share_url=f"/share/{share_link.token}",
        assessment_id=assessment_id,
        expires_at=share_link.expires_at.isoformat(),
        is_valid=share_link.is_valid(),
        access_count=share_link.access_count
    )


@router.get("/{token}", response_model=SharedAssessmentResponse)
async def access_shared_assessment(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Access a shared assessment via its share token.

    This is a public endpoint - no authentication required.
    Returns the assessment details if the link is valid and not expired.
    """
    # Find share link
    result = await db.execute(
        select(ShareLink).where(ShareLink.token == token)
    )
    share_link = result.scalar_one_or_none()

    if not share_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found"
        )

    if not share_link.is_valid():
        if share_link.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This share link has been revoked"
            )
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This share link has expired"
        )

    # Get assessment
    assessment_result = await db.execute(
        select(Assessment).where(Assessment.id == share_link.assessment_id)
    )
    assessment = assessment_result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )

    # Get creator name
    from app.models.user import User
    creator_result = await db.execute(
        select(User).where(User.id == share_link.created_by)
    )
    creator = creator_result.scalar_one_or_none()
    shared_by = creator.full_name if creator else "Unknown"

    # Record access
    share_link.record_access()
    await db.commit()

    # Extract relevant data from assessment
    ai_analysis = assessment.ai_analysis or {}

    return SharedAssessmentResponse(
        assessment_id=assessment.id,
        insured_name=assessment.insured_name,
        risk_category=assessment.risk_category.value if assessment.risk_category else None,
        status=assessment.status,
        decision=assessment.decision or ai_analysis.get("decision"),
        decision_rationale=assessment.decision_rationale or ai_analysis.get("decision_rationale"),
        risk_score=assessment.risk_score,
        confidence_score=assessment.confidence_score,
        underwriting_percentage=ai_analysis.get("underwriting_percentage"),
        premium_price=ai_analysis.get("premium_price"),
        risk_analysis=ai_analysis.get("risk_analysis"),
        created_at=assessment.created_at.isoformat() if assessment.created_at else "",
        shared_by=shared_by,
        expires_at=share_link.expires_at.isoformat()
    )


@router.delete("/{token}")
async def revoke_share_link(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Revoke a share link.

    Only the creator of the link or an admin can revoke it.
    """
    # Find share link
    result = await db.execute(
        select(ShareLink).where(ShareLink.token == token)
    )
    share_link = result.scalar_one_or_none()

    if not share_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found"
        )

    # Check ownership
    if share_link.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only revoke your own share links"
        )

    # Revoke
    share_link.revoke()
    await db.commit()

    return {"message": "Share link revoked successfully"}


@router.get("/assessments/{assessment_id}/links")
async def list_assessment_share_links(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all share links for an assessment.

    Returns both active and expired/revoked links.
    """
    # Check if assessment exists and user has access
    assessment_result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = assessment_result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )

    if assessment.created_by != current_user.id and current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view share links for your own assessments"
        )

    # Get share links
    result = await db.execute(
        select(ShareLink)
        .where(ShareLink.assessment_id == assessment_id)
        .order_by(ShareLink.created_at.desc())
    )
    share_links = result.scalars().all()

    return {
        "assessment_id": assessment_id,
        "total_links": len(share_links),
        "links": [
            {
                "token": link.token,
                "share_url": f"/share/{link.token}",
                "created_at": link.created_at.isoformat(),
                "expires_at": link.expires_at.isoformat(),
                "is_valid": link.is_valid(),
                "is_revoked": link.is_revoked,
                "access_count": link.access_count,
                "last_accessed_at": link.last_accessed_at.isoformat() if link.last_accessed_at else None
            }
            for link in share_links
        ]
    }
