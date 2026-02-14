"""
InstantRisk Engine - Clauses Library API Router

Provides RESTful endpoints for accessing the comprehensive clauses library
with 11,000+ insurance and contract clauses.

Endpoints:
- GET /clauses/library - Search and browse clauses with pagination
- GET /clauses/categories - Get all clause categories with counts
- GET /clauses/{clause_id} - Get a single clause by ID
- GET /clauses/statistics - Get library statistics
- POST /clauses/recommend/{assessment_id} - Get recommended clauses for an assessment
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
    source: Optional[str] = Query(None, description="Filter by source (ledgar, cuad, contract_nli, templates)"),
    line_of_business: Optional[str] = Query(None, description="Filter by line of business"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """
    Search and browse the InstantRisk Engine clauses library.

    Provides access to 11,000+ clauses from multiple sources:
    - LEDGAR: Legal provisions in 100 categories
    - CUAD: Contract clauses with 41 types
    - ContractNLI: Contract NLI clauses
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
    Get InstantRisk Engine recommended clauses for an assessment.

    Analyzes the assessment data and recommends relevant clauses with explanations.
    Searches 11,000+ real clauses from LEDGAR, CUAD, and ContractNLI datasets.
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
        seen_ids = set()

        def add_rec(clause, score, reason, mandatory=False):
            if clause["id"] not in seen_ids:
                seen_ids.add(clause["id"])
                recommendations.append(RecommendedClause(
                    clause=ClauseSummary(**clause),
                    relevance_score=score,
                    reason=reason,
                    is_mandatory=mandatory
                ))

        # 1. Risk-category specific searches (search by TEXT, not by category field)
        risk_search_map = {
            "cyber": ["cyber liability", "data breach", "network security", "privacy"],
            "marine": ["marine cargo", "hull", "maritime", "voyage"],
            "property": ["property damage", "fire", "natural disaster", "building"],
            "casualty": ["casualty", "bodily injury", "personal injury"],
            "professional": ["professional indemnity", "errors omissions", "malpractice"],
            "aviation": ["aviation", "aircraft", "hull war"],
            "energy": ["energy", "offshore", "oil gas"],
            "financial": ["financial loss", "fidelity", "crime"],
            "motor": ["motor vehicle", "automobile", "fleet"],
            "liability": ["general liability", "public liability", "product liability"],
        }
        search_terms = risk_search_map.get(risk_category, [risk_category]) if risk_category else []
        for term in search_terms[:3]:
            results, _ = clauses_library_service.search(query=term, page_size=5)
            for clause in results:
                add_rec(clause, 0.85, f"Relevant to {risk_category} insurance: '{term}'")

        # 3. Standard insurance clauses every policy needs
        standard_searches = [
            ("indemnification", 0.8, "Standard indemnification provision"),
            ("limitation of liability", 0.8, "Liability limitation clause"),
            ("termination", 0.75, "Contract termination provisions"),
            ("governing law", 0.75, "Governing law and jurisdiction"),
            ("confidentiality", 0.7, "Confidentiality obligations"),
            ("warranties", 0.7, "Warranty provisions"),
            ("notice", 0.65, "Notice requirements"),
            ("assignment", 0.65, "Assignment and transfer provisions"),
        ]
        for query, score, reason in standard_searches:
            results, _ = clauses_library_service.search(query=query, page_size=3)
            for clause in results:
                add_rec(clause, score, reason)

        # 4. Search terms from summary/extracted data
        if summary:
            for term in ["cyber", "marine", "property", "liability", "professional",
                         "terrorism", "war", "flood", "earthquake", "pandemic",
                         "directors", "officers", "employment", "trade credit"]:
                if term in summary.lower():
                    results, _ = clauses_library_service.search(query=term, page_size=3)
                    for clause in results:
                        add_rec(clause, 0.7, f"Related to '{term}' in assessment")

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
