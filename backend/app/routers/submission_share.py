"""
InstantRisk V2 - Submission Share Router

API endpoints for sharing submissions/assessments between internal users.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.models.submission_share import SubmissionShare, ShareType

router = APIRouter(prefix="/shares", tags=["Submission Sharing"])

logger = logging.getLogger("instantrisk.sharing")


class SubmissionShareCreate(BaseModel):
    """Request schema for creating a submission share."""

    assessment_id: str
    shared_with_user_id: str
    share_type: ShareType = ShareType.ANALYSIS
    include_documents: bool = True
    message: Optional[str] = None


class SubmissionShareResponse(BaseModel):
    """Response schema for a submission share."""

    id: str
    assessment_id: str
    shared_by: str
    shared_by_name: str
    shared_with: str
    shared_with_name: str
    share_type: ShareType
    include_documents: bool
    message: Optional[str]
    created_at: str
    is_revoked: bool

    class Config:
        from_attributes = True


class AssessmentSummary(BaseModel):
    """Summary of an assessment for sharing."""

    id: str
    reference_number: Optional[str]
    insured_name: Optional[str]
    risk_category: Optional[str]
    status: str
    decision: Optional[str]
    risk_score: Optional[int]
    created_at: str


class SharedAssessmentWithDetails(BaseModel):
    """Assessment with share details."""

    share: SubmissionShareResponse
    assessment: AssessmentSummary


class UserSearchResult(BaseModel):
    """User search result."""

    id: str
    full_name: str
    email: str
    role: str


@router.post(
    "", response_model=SubmissionShareResponse, status_code=status.HTTP_201_CREATED
)
async def create_submission_share(
    share: SubmissionShareCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Share a submission with another user."""
    if share.shared_with_user_id == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot share with yourself"
        )

    result = await db.execute(
        select(Assessment).where(Assessment.id == share.assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    result = await db.execute(select(User).where(User.id == share.shared_with_user_id))
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recipient user not found"
        )

    existing = await db.execute(
        select(SubmissionShare).where(
            SubmissionShare.assessment_id == share.assessment_id,
            SubmissionShare.shared_by == current_user.id,
            SubmissionShare.shared_with == share.shared_with_user_id,
            SubmissionShare.is_revoked == False,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already shared with this user",
        )

    new_share = SubmissionShare(
        assessment_id=share.assessment_id,
        shared_by=current_user.id,
        shared_with=share.shared_with_user_id,
        share_type=share.share_type,
        include_documents=share.include_documents,
        message=share.message,
    )
    db.add(new_share)
    await db.commit()
    await db.refresh(new_share)

    return SubmissionShareResponse(
        id=str(new_share.id),
        assessment_id=str(new_share.assessment_id),
        shared_by=str(new_share.shared_by),
        shared_by_name=current_user.full_name or current_user.email,
        shared_with=str(new_share.shared_with),
        shared_with_name=recipient.full_name or recipient.email,
        share_type=new_share.share_type,
        include_documents=new_share.include_documents,
        message=new_share.message,
        created_at=new_share.created_at.isoformat(),
        is_revoked=new_share.is_revoked,
    )


@router.get("/received", response_model=List[SharedAssessmentWithDetails])
async def get_received_shares(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get all submissions shared with the current user."""
    result = await db.execute(
        select(SubmissionShare)
        .where(
            SubmissionShare.shared_with == current_user.id,
            SubmissionShare.is_revoked == False,
        )
        .order_by(SubmissionShare.created_at.desc())
    )
    shares = result.scalars().all()

    response = []
    for share in shares:
        result = await db.execute(
            select(Assessment).where(Assessment.id == share.assessment_id)
        )
        assessment = result.scalar_one_or_none()
        if assessment:
            sharer_result = await db.execute(
                select(User).where(User.id == share.shared_by)
            )
            sharer = sharer_result.scalar_one_or_none()

            response.append(
                SharedAssessmentWithDetails(
                    share=SubmissionShareResponse(
                        id=str(share.id),
                        assessment_id=str(share.assessment_id),
                        shared_by=str(share.shared_by),
                        shared_by_name=sharer.full_name or sharer.email
                        if sharer
                        else "Unknown",
                        shared_with=str(share.shared_with),
                        shared_with_name=current_user.full_name or current_user.email,
                        share_type=share.share_type,
                        include_documents=share.include_documents,
                        message=share.message,
                        created_at=share.created_at.isoformat(),
                        is_revoked=share.is_revoked,
                    ),
                    assessment=AssessmentSummary(
                        id=str(assessment.id),
                        reference_number=assessment.reference_number,
                        insured_name=assessment.insured_name,
                        risk_category=assessment.risk_category,
                        status=assessment.status,
                        decision=assessment.decision,
                        risk_score=assessment.risk_score,
                        created_at=assessment.created_at.isoformat()
                        if assessment.created_at
                        else "",
                    ),
                )
            )

    return response


@router.get("/sent", response_model=List[SharedAssessmentWithDetails])
async def get_sent_shares(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get all submissions shared by the current user."""
    result = await db.execute(
        select(SubmissionShare)
        .where(
            SubmissionShare.shared_by == current_user.id,
            SubmissionShare.is_revoked == False,
        )
        .order_by(SubmissionShare.created_at.desc())
    )
    shares = result.scalars().all()

    response = []
    for share in shares:
        result = await db.execute(
            select(Assessment).where(Assessment.id == share.assessment_id)
        )
        assessment = result.scalar_one_or_none()
        if assessment:
            recipient_result = await db.execute(
                select(User).where(User.id == share.shared_with)
            )
            recipient = recipient_result.scalar_one_or_none()

            response.append(
                SharedAssessmentWithDetails(
                    share=SubmissionShareResponse(
                        id=str(share.id),
                        assessment_id=str(share.assessment_id),
                        shared_by=str(share.shared_by),
                        shared_by_name=current_user.full_name or current_user.email,
                        shared_with=str(share.shared_with),
                        shared_with_name=recipient.full_name or recipient.email
                        if recipient
                        else "Unknown",
                        share_type=share.share_type,
                        include_documents=share.include_documents,
                        message=share.message,
                        created_at=share.created_at.isoformat(),
                        is_revoked=share.is_revoked,
                    ),
                    assessment=AssessmentSummary(
                        id=str(assessment.id),
                        reference_number=assessment.reference_number,
                        insured_name=assessment.insured_name,
                        risk_category=assessment.risk_category,
                        status=assessment.status,
                        decision=assessment.decision,
                        risk_score=assessment.risk_score,
                        created_at=assessment.created_at.isoformat()
                        if assessment.created_at
                        else "",
                    ),
                )
            )

    return response


@router.get("/received/count")
async def get_received_shares_count(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get count of submissions shared with the current user."""
    result = await db.execute(
        select(func.count(SubmissionShare.id)).where(
            SubmissionShare.shared_with == current_user.id,
            SubmissionShare.is_revoked == False,
        )
    )
    count = result.scalar() or 0
    return {"count": count}


@router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    share_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke a submission share."""
    result = await db.execute(
        select(SubmissionShare).where(SubmissionShare.id == share_id)
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Share not found"
        )

    if share.shared_by != current_user.id and share.shared_with != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to revoke this share",
        )

    share.is_revoked = True
    await db.commit()

    return None


@router.get("/users/search", response_model=List[UserSearchResult])
async def search_users(
    q: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search for users to share with."""
    search_term = f"%{q}%"
    result = await db.execute(
        select(User)
        .where(
            User.id != current_user.id,
            or_(User.email.ilike(search_term), User.full_name.ilike(search_term)),
            User.is_active == True,
        )
        .limit(20)
    )
    users = result.scalars().all()

    return [
        UserSearchResult(
            id=str(user.id),
            full_name=user.full_name or "",
            email=user.email,
            role=user.role or "user",
        )
        for user in users
    ]
