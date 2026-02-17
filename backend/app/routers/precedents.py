"""
Precedent Search Router

API endpoints for finding similar historical assessments.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.services.precedent_search import precedent_search_service

router = APIRouter()


# Response schemas
class SimilarAssessment(BaseModel):
    """Similar assessment with similarity score."""
    assessment_id: str
    reference_number: Optional[str]
    risk_category: str
    territory: Optional[str]
    insured_name: Optional[str]
    decision: str
    premium: Optional[float]
    sum_insured: Optional[float]
    created_at: str
    similarity: float
    similarity_pct: str


class PrecedentSearchResponse(BaseModel):
    """Precedent search results."""
    query_assessment_id: str
    similar_assessments: List[SimilarAssessment]
    count: int


@router.get(
    "/similar/{assessment_id}",
    response_model=PrecedentSearchResponse,
    summary="Find similar assessments"
)
async def find_similar_assessments(
    assessment_id: UUID,
    top_k: int = Query(5, ge=1, le=20, description="Number of results"),
    min_similarity: float = Query(0.7, ge=0.0, le=1.0, description="Minimum similarity"),
    same_category_only: bool = Query(False, description="Only same risk category"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Find similar historical assessments for learning and comparison.

    Uses semantic vector search to find assessments with similar:
    - Risk characteristics
    - Coverage requirements
    - Territory/jurisdiction
    - Insured profile

    Helps underwriters:
    - Learn from past decisions
    - Ensure consistency
    - Validate pricing
    - Identify precedents
    """

    # Check assessment exists
    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found"
        )

    # Build filters
    filters = {}
    if same_category_only and assessment.risk_category:
        filters["risk_category"] = assessment.risk_category

    # Search
    similar = await precedent_search_service.find_similar(
        db=db,
        assessment_id=assessment_id,
        top_k=top_k,
        min_similarity=min_similarity,
        filters=filters
    )

    return PrecedentSearchResponse(
        query_assessment_id=str(assessment_id),
        similar_assessments=similar,
        count=len(similar)
    )


@router.post(
    "/embed/{assessment_id}",
    summary="Embed assessment for precedent search"
)
async def embed_assessment(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create vector embedding for an assessment.

    Called automatically after assessment creation/update.
    Can also be called manually to re-embed.
    """

    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found"
        )

    vector = await precedent_search_service.embed_assessment(db, assessment)

    return {
        "message": "Assessment embedded successfully",
        "assessment_id": str(assessment_id),
        "embedding_dim": 768
    }


@router.post(
    "/batch-embed",
    summary="Batch embed all assessments"
)
async def batch_embed_assessments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Embed all existing assessments that don't have vectors yet.

    Run this once after deploying precedent search to populate
    vectors for historical assessments.
    """

    # Check admin permission
    if current_user.role.lower() not in ('admin', 'superadmin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    count = await precedent_search_service.embed_all_assessments(db)

    return {
        "message": f"Batch embedding complete",
        "assessments_embedded": count
    }
