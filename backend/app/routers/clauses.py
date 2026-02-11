"""
InstantRisk V3 - Clauses Library API Router

Provides RESTful endpoints for accessing the comprehensive clauses library
with 102,000+ insurance and contract clauses.

Endpoints:
- GET /clauses/library - Search and browse clauses with pagination
- GET /clauses/categories - Get all clause categories with counts
- GET /clauses/{clause_id} - Get a single clause by ID
- GET /clauses/statistics - Get library statistics
- POST /clauses/recommend/{assessment_id} - Get AI-recommended clauses for an assessment
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.clauses_library_service import clauses_library_service
from app.models.assessment import Assessment

router = APIRouter(prefix="/clauses", tags=["Clauses Library"])


# =============================================================================
# Response Schemas
# =============================================================================

class ClauseSummary(BaseModel):
    """Summary of a clause for list views."""
    id: str
    name: str
    category: str
    source: str
    clause_type: Optional[str] = None
    line_of_business: Optional[str] = None
    typical_use: Optional[str] = None
    form_number: Optional[str] = None
    is_exclusion: bool = False
    is_mandatory: bool = False
    text_preview: Optional[str] = None


class ClauseDetail(ClauseSummary):
    """Full clause detail with complete text."""
    text: str


class ClauseCategory(BaseModel):
    """Clause category with count."""
    id: str
    name: str
    count: int


class ClausesLibraryResponse(BaseModel):
    """Response for clauses library search."""
    items: List[ClauseSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class CategoriesResponse(BaseModel):
    """Response for categories listing."""
    categories: List[ClauseCategory]
    total: int


class LibraryStatistics(BaseModel):
    """Library statistics."""
    total_clauses: int
    total_categories: int
    sources: dict
    top_categories: List[dict]


class RecommendedClause(BaseModel):
    """A recommended clause with relevance explanation."""
    clause: ClauseSummary
    relevance_score: float = Field(ge=0, le=1)
    reason: str
    is_mandatory: bool = False


class ClauseRecommendationsResponse(BaseModel):
    """Response for clause recommendations."""
    assessment_id: str
    recommended_clauses: List[RecommendedClause]
    mandatory_count: int
    optional_count: int


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/library", response_model=ClausesLibraryResponse)
async def get_clauses_library(
    search: Optional[str] = Query(None, description="Search query for clause name or text"),
    category: Optional[str] = Query(None, description="Filter by category"),
    source: Optional[str] = Query(None, description="Filter by source (lma, ledgar, cuad, contract_nli, templates)"),
    line_of_business: Optional[str] = Query(None, description="Filter by line of business"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """
    Search and browse the clauses library.

    Provides access to 102,000+ clauses from multiple sources:
    - LMA: 33 Lloyd's Market Association clauses
    - LEDGAR: 80,000 legal provisions in 100 categories
    - CUAD: 12,422 contract clauses with 41 types
    - ContractNLI: 10,319 contract NLI clauses
    - Templates: Curated insurance clause templates

    Supports full-text search, category filtering, and pagination.
    """
    try:
        clauses, total = clauses_library_service.search(
            query=search,
            category=category,
            source=source,
            line_of_business=line_of_business,
            page=page,
            page_size=page_size
        )

        total_pages = (total + page_size - 1) // page_size

        return ClausesLibraryResponse(
            items=[ClauseSummary(**c) for c in clauses],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching clauses: {str(e)}")


@router.get("/categories", response_model=CategoriesResponse)
async def get_clause_categories():
    """
    Get all clause categories with counts.

    Returns 100+ categories from all sources, sorted by count descending.
    """
    try:
        categories = clauses_library_service.get_categories()

        return CategoriesResponse(
            categories=[ClauseCategory(**c) for c in categories],
            total=len(categories)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting categories: {str(e)}")


@router.get("/statistics", response_model=LibraryStatistics)
async def get_library_statistics():
    """
    Get library statistics.

    Returns total counts, source breakdown, and top categories.
    """
    try:
        stats = clauses_library_service.get_statistics()
        return LibraryStatistics(**stats)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting statistics: {str(e)}")


@router.get("/{clause_id}", response_model=ClauseDetail)
async def get_clause_detail(clause_id: str):
    """
    Get a single clause by ID with full text.
    """
    try:
        clause = clauses_library_service.get_clause_by_id(clause_id)

        if not clause:
            raise HTTPException(status_code=404, detail=f"Clause not found: {clause_id}")

        return ClauseDetail(**clause)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting clause: {str(e)}")


@router.post("/recommend/{assessment_id}", response_model=ClauseRecommendationsResponse)
async def recommend_clauses_for_assessment(
    assessment_id: str,
    max_recommendations: int = Query(20, ge=5, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-recommended clauses for an assessment.

    Analyzes the assessment data and recommends relevant clauses with explanations.
    Returns mandatory clauses first, then recommended optional clauses.
    """
    try:
        # Get assessment
        result = await db.execute(
            Assessment.__table__.select().where(Assessment.id == assessment_id)
        )
        assessment = result.first()

        if not assessment:
            raise HTTPException(status_code=404, detail=f"Assessment not found: {assessment_id}")

        # Extract assessment data
        assessment_dict = dict(assessment._mapping)
        risk_category = assessment_dict.get("risk_category", "").lower()
        territory = assessment_dict.get("territory", "")
        summary = assessment_dict.get("summary", "")
        extracted_data = assessment_dict.get("extracted_data", {}) or {}

        # Build search queries based on assessment
        recommendations = []

        # 1. Get mandatory clauses (sanctions, several liability, etc.)
        # Search for sanctions clauses
        sanctions_clauses, _ = clauses_library_service.search(
            query="sanction",
            source="lma",
            page_size=10
        )
        for clause in sanctions_clauses:
            if clause.get("is_mandatory"):
                recommendations.append(RecommendedClause(
                    clause=ClauseSummary(**clause),
                    relevance_score=1.0,
                    reason="Mandatory sanctions clause required for Lloyd's policies",
                    is_mandatory=True
                ))

        # Search for several liability clause
        liability_clauses, _ = clauses_library_service.search(
            query="several liability",
            source="lma",
            page_size=5
        )
        for clause in liability_clauses:
            if clause.get("is_mandatory") and clause["id"] not in [r.clause.id for r in recommendations]:
                recommendations.append(RecommendedClause(
                    clause=ClauseSummary(**clause),
                    relevance_score=1.0,
                    reason="Mandatory several liability clause required for Lloyd's policies",
                    is_mandatory=True
                ))

        # 2. Get risk-category specific clauses
        if risk_category:
            category_clauses, _ = clauses_library_service.search(
                category=risk_category,
                page_size=10
            )
            for clause in category_clauses:
                if clause["id"] not in [r.clause.id for r in recommendations]:
                    recommendations.append(RecommendedClause(
                        clause=ClauseSummary(**clause),
                        relevance_score=0.9,
                        reason=f"Recommended for {risk_category} risks",
                        is_mandatory=False
                    ))

        # 3. Search for relevant clauses based on summary
        if summary:
            # Extract key terms from summary
            key_terms = []
            for term in ["cyber", "marine", "property", "liability", "professional", "terrorism", "war"]:
                if term in summary.lower():
                    key_terms.append(term)

            for term in key_terms:
                term_clauses, _ = clauses_library_service.search(
                    query=term,
                    page_size=5
                )
                for clause in term_clauses:
                    if clause["id"] not in [r.clause.id for r in recommendations]:
                        recommendations.append(RecommendedClause(
                            clause=ClauseSummary(**clause),
                            relevance_score=0.7,
                            reason=f"Related to '{term}' mentioned in assessment",
                            is_mandatory=False
                        ))

        # 4. Get exclusion clauses
        exclusion_clauses, _ = clauses_library_service.search(
            query="exclusion",
            page_size=5
        )
        for clause in exclusion_clauses:
            if clause["id"] not in [r.clause.id for r in recommendations] and clause.get("is_exclusion"):
                recommendations.append(RecommendedClause(
                    clause=ClauseSummary(**clause),
                    relevance_score=0.6,
                    reason="Standard exclusion clause",
                    is_mandatory=False
                ))

        # Limit to max_recommendations
        recommendations = recommendations[:max_recommendations]

        # Count mandatory vs optional
        mandatory_count = len([r for r in recommendations if r.is_mandatory])
        optional_count = len(recommendations) - mandatory_count

        return ClauseRecommendationsResponse(
            assessment_id=assessment_id,
            recommended_clauses=recommendations,
            mandatory_count=mandatory_count,
            optional_count=optional_count
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recommending clauses: {str(e)}")
