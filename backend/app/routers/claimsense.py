"""
ClaimSense Router

API endpoints for benchmark loss run queries and comparisons.
"""
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.claimsense_service import get_claimsense_service

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class BenchmarkQueryParams(BaseModel):
    """Query parameters for benchmark data."""
    policy_type: str = Field(..., description="Policy type: GL, WC, AL, PR, PL, CY, DO, EPL")
    state: Optional[str] = Field(None, max_length=2, description="Two-letter state code")
    industry: Optional[str] = Field(None, description="Industry name or NAICS code")
    years: Optional[List[int]] = Field(None, description="Specific policy years")
    min_year: Optional[int] = Field(None, description="Minimum policy year")
    max_year: Optional[int] = Field(None, description="Maximum policy year")


class BenchmarkResponse(BaseModel):
    """Benchmark query response."""
    policy_type: str
    state: Optional[str]
    industry: Optional[str]
    years: List[int]
    total_claims: int
    total_paid: float
    total_reserved: float
    total_incurred: float
    average_severity: float
    median_severity: float
    percentiles: Dict[str, float]
    claim_frequency_per_year: float
    claims_by_type: Dict[str, Dict[str, Any]]
    claims_by_year: Dict[str, Dict[str, Any]]
    years_of_data: int


class InsuredLossResponse(BaseModel):
    """Insured loss history response."""
    assessment_id: str
    total_claims: int
    open_claims: int
    closed_claims: int
    total_paid: float
    total_reserved: float
    total_incurred: float
    average_severity: float
    median_severity: float
    largest_claim: float
    claim_frequency_per_year: float
    claims_by_type: Dict[str, Dict[str, Any]]
    years_of_history: int
    years: List[int]


class ComparisonResponse(BaseModel):
    """Comparison response with narrative."""
    assessment_id: str
    insured: Dict[str, Any]
    benchmark: Dict[str, Any]
    narrative: str
    metrics: Dict[str, Any]


class NLQueryRequest(BaseModel):
    """Natural language query request."""
    question: str = Field(..., min_length=5, max_length=500)
    assessment_id: Optional[str] = None
    policy_type: Optional[str] = None
    state: Optional[str] = None


class NLQueryResponse(BaseModel):
    """Natural language query response."""
    query_type: str
    parameters: Dict[str, Any]
    result: Dict[str, Any]


# Endpoints
@router.get("/benchmark", response_model=BenchmarkResponse)
async def get_benchmark_data(
    policy_type: str = Query(..., description="Policy type: GL, WC, AL, PR, PL, CY, DO, EPL"),
    state: Optional[str] = Query(None, max_length=2),
    industry: Optional[str] = Query(None),
    years: Optional[str] = Query(None, description="Comma-separated years"),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Query benchmark loss run data.

    Returns aggregated statistics for the specified policy type, state, and industry.
    Data is sourced from the ClaimSense benchmark database (18K+ records).
    """
    # Validate policy type
    valid_types = ["GL", "WC", "AL", "PR", "PL", "CY", "DO", "EPL"]
    if policy_type.upper() not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid policy type. Must be one of: {', '.join(valid_types)}",
        )

    # Parse years if provided
    year_list = None
    if years:
        try:
            year_list = [int(y.strip()) for y in years.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid years format. Use comma-separated integers.",
            )

    service = get_claimsense_service(db)
    result = await service.query_benchmark(
        policy_type=policy_type.upper(),
        state=state.upper() if state else None,
        industry=industry,
        years=year_list,
        min_year=min_year,
        max_year=max_year,
    )

    data = result.to_dict()

    return BenchmarkResponse(
        policy_type=result.policy_type,
        state=result.state,
        industry=result.industry,
        years=result.years,
        total_claims=data.get("total_claims", 0),
        total_paid=data.get("total_paid", 0),
        total_reserved=data.get("total_reserved", 0),
        total_incurred=data.get("total_incurred", 0),
        average_severity=data.get("average_severity", 0),
        median_severity=data.get("median_severity", 0),
        percentiles=data.get("percentiles", {}),
        claim_frequency_per_year=data.get("claim_frequency_per_year", 0),
        claims_by_type=data.get("claims_by_type", {}),
        claims_by_year=data.get("claims_by_year", {}),
        years_of_data=data.get("years_of_data", 0),
    )


@router.get("/insured/{assessment_id}", response_model=InsuredLossResponse)
async def get_insured_loss_history(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get aggregated loss history for an assessment.

    Returns statistics calculated from uploaded loss run documents.
    """
    service = get_claimsense_service(db)
    result = await service.query_insured(assessment_id)

    if result.get("total_claims", 0) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No loss history found for this assessment. Upload loss run documents first.",
        )

    return InsuredLossResponse(
        assessment_id=result["assessment_id"],
        total_claims=result.get("total_claims", 0),
        open_claims=result.get("open_claims", 0),
        closed_claims=result.get("closed_claims", 0),
        total_paid=result.get("total_paid", 0),
        total_reserved=result.get("total_reserved", 0),
        total_incurred=result.get("total_incurred", 0),
        average_severity=result.get("average_severity", 0),
        median_severity=result.get("median_severity", 0),
        largest_claim=result.get("largest_claim", 0),
        claim_frequency_per_year=result.get("claim_frequency_per_year", 0),
        claims_by_type=result.get("claims_by_type", {}),
        years_of_history=result.get("years_of_history", 0),
        years=result.get("years", []),
    )


@router.get("/compare/{assessment_id}", response_model=ComparisonResponse)
async def compare_insured_to_benchmark(
    assessment_id: str,
    policy_type: str = Query(..., description="Policy type for benchmark comparison"),
    state: Optional[str] = Query(None, max_length=2),
    industry: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compare insured loss history against benchmark data.

    Returns side-by-side comparison with AI-generated narrative analysis
    highlighting how the insured compares to industry peers.
    """
    service = get_claimsense_service(db)
    result = await service.compare(
        assessment_id=assessment_id,
        policy_type=policy_type.upper(),
        state=state.upper() if state else None,
        industry=industry,
    )

    return ComparisonResponse(
        assessment_id=result.assessment_id,
        insured=result.insured_summary,
        benchmark=result.benchmark_summary,
        narrative=result.narrative,
        metrics=result.metrics,
    )


@router.post("/query", response_model=NLQueryResponse)
async def natural_language_query(
    request: NLQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process natural language query about claims data.

    Examples:
    - "What is the average GL severity in California?"
    - "How does this insured compare to industry benchmarks?"
    - "Show me workers comp trends in manufacturing"
    """
    service = get_claimsense_service(db)

    context = {}
    if request.assessment_id:
        context["assessment_id"] = request.assessment_id
    if request.policy_type:
        context["policy_type"] = request.policy_type
    if request.state:
        context["state"] = request.state

    result = await service.nl_query(
        question=request.question,
        context=context,
    )

    return NLQueryResponse(
        query_type=result["query_type"],
        parameters=result["parameters"],
        result=result["result"],
    )


@router.get("/policy-types")
async def list_policy_types(
    current_user: User = Depends(get_current_user),
):
    """List available policy types for benchmark queries."""
    return {
        "policy_types": [
            {"code": "GL", "name": "General Liability"},
            {"code": "WC", "name": "Workers Compensation"},
            {"code": "AL", "name": "Auto Liability"},
            {"code": "PR", "name": "Property"},
            {"code": "PL", "name": "Professional Liability"},
            {"code": "CY", "name": "Cyber"},
            {"code": "DO", "name": "Directors & Officers"},
            {"code": "EPL", "name": "Employment Practices Liability"},
        ]
    }


@router.get("/states")
async def list_states(
    policy_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List states with available benchmark data."""
    # In production, this would query distinct states from benchmark_loss_runs
    # For now, return common states
    return {
        "states": [
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
        ]
    }
