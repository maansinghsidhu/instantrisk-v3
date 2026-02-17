"""
InstantRisk V2 - Entity Relationship Graph Router

Endpoints for building and querying corporate ownership graphs
and detecting fraud patterns using Neo4j / NetworkX.

Routes:
    POST /api/v1/entities/build-graph/{company_name}
    GET  /api/v1/entities/graph/{company_name}
    GET  /api/v1/entities/related/{assessment_id}
    POST /api/v1/entities/detect-fraud
"""

import uuid
import logging
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.services.entity_graph_service import (
    build_entity_graph,
    get_entity_graph,
    entity_graph_to_dict,
    EntityGraph,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================

class BuildGraphRequest(BaseModel):
    """Optional parameters for graph building."""
    depth: int = Field(default=2, ge=1, le=3, description="Ownership traversal depth (1-3)")
    include_officers: bool = Field(default=True, description="Include directors and officers")
    include_psc: bool = Field(default=True, description="Include Persons with Significant Control")


class BuildGraphResponse(BaseModel):
    """Response when graph build is triggered."""
    job_id: str
    company_name: str
    status: str
    message: str


class EntityNode(BaseModel):
    """Single entity in the graph."""
    entity_id: str
    name: str
    entity_type: str
    jurisdiction: str
    registration_number: str
    incorporation_date: str
    address: str
    status: str
    source: str


class RelationshipEdge(BaseModel):
    """Single relationship between entities."""
    from_id: str
    to_id: str
    relationship_type: str
    ownership_pct: float
    start_date: str
    source: str


class FraudSignalSchema(BaseModel):
    """A detected fraud indicator."""
    signal_type: str
    severity: str
    description: str
    entities_involved: List[str]
    confidence: float


class EntityGraphResponse(BaseModel):
    """Full entity graph response."""
    root_company: str
    built_at: str
    sources_used: List[str]
    overall_fraud_score: int
    risk_level: str
    entity_count: int
    relationship_count: int
    fraud_signal_count: int
    entities: List[EntityNode]
    relationships: List[RelationshipEdge]
    fraud_signals: List[FraudSignalSchema]
    errors: List[str]


class RelatedEntitiesResponse(BaseModel):
    """Related entities for an assessment."""
    assessment_id: str
    company_name: str
    graph_available: bool
    fraud_score: Optional[int]
    risk_level: Optional[str]
    key_signals: List[Dict[str, Any]]
    message: str


class FraudDetectionRequest(BaseModel):
    """Request to run fraud detection on a specific set of entities."""
    company_names: List[str] = Field(..., min_length=1, max_length=10,
                                     description="List of company names to analyse (max 10)")
    depth: int = Field(default=1, ge=1, le=2, description="Graph depth for each company")


class FraudDetectionResponse(BaseModel):
    """Aggregated fraud detection results for multiple companies."""
    companies_analysed: int
    total_entities: int
    total_relationships: int
    total_signals: int
    highest_risk_company: str
    highest_fraud_score: int
    overall_risk_level: str
    results: List[Dict[str, Any]]


# =============================================================================
# In-memory job store for background build tasks
# (In production this would be Redis or a DB table)
# =============================================================================

_build_jobs: Dict[str, Dict[str, Any]] = {}


async def _run_build_job(job_id: str, company_name: str, depth: int):
    """Background task that builds the entity graph and stores result."""
    _build_jobs[job_id]["status"] = "in_progress"
    _build_jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()
    try:
        graph = await build_entity_graph(company_name, depth=depth)
        graph_dict = entity_graph_to_dict(graph)
        _build_jobs[job_id]["status"] = "completed"
        _build_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        _build_jobs[job_id]["result"] = graph_dict
        _build_jobs[job_id]["fraud_score"] = graph.overall_fraud_score
        _build_jobs[job_id]["risk_level"] = graph.risk_level
        logger.info(f"Graph build job {job_id} completed: score={graph.overall_fraud_score}")
    except Exception as e:
        logger.error(f"Graph build job {job_id} failed: {e}")
        _build_jobs[job_id]["status"] = "failed"
        _build_jobs[job_id]["error"] = str(e)


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/build-graph/{company_name}",
    response_model=BuildGraphResponse,
    summary="Build entity relationship graph",
    description=(
        "Trigger background build of a corporate ownership graph for the given company. "
        "Pulls data from OpenCorporates, Companies House (UK), and SEC EDGAR. "
        "Poll /entities/graph/{company_name} or the returned job_id for results."
    ),
    status_code=status.HTTP_202_ACCEPTED,
)
async def build_graph(
    company_name: str,
    background_tasks: BackgroundTasks,
    params: BuildGraphRequest = None,
    current_user: User = Depends(get_current_user),
):
    """
    Build a corporate ownership graph for fraud detection.

    The graph is built asynchronously. Returns a job_id you can use to poll
    GET /entities/graph/{company_name} for the completed result.

    Args:
        company_name: Name of the company to investigate (URL-encoded)
        params: Optional depth and feature flags
        current_user: Authenticated user

    Returns:
        Job tracking information
    """
    if params is None:
        params = BuildGraphRequest()

    # Sanitise company name
    clean_name = company_name.strip()
    if len(clean_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company name must be at least 2 characters",
        )

    job_id = f"graph-{uuid.uuid4().hex[:12]}"

    _build_jobs[job_id] = {
        "job_id": job_id,
        "company_name": clean_name,
        "status": "queued",
        "depth": params.depth,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": str(current_user.id),
        "result": None,
        "error": None,
    }

    background_tasks.add_task(_run_build_job, job_id, clean_name, params.depth)

    return BuildGraphResponse(
        job_id=job_id,
        company_name=clean_name,
        status="queued",
        message=(
            f"Graph build started for '{clean_name}'. "
            f"Polling GET /api/v1/entities/graph/{company_name} for results. "
            f"Job ID: {job_id}"
        ),
    )


@router.get(
    "/job/{job_id}",
    summary="Check graph build job status",
    description="Check the status and result of a graph build job.",
)
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Check status of a background graph build job.

    Args:
        job_id: Job ID returned by POST /entities/build-graph/{company_name}

    Returns:
        Job status dict with result when completed
    """
    job = _build_jobs.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    # Return lightweight status without full graph in in-progress state
    if job["status"] in ("queued", "in_progress"):
        return {
            "job_id": job_id,
            "company_name": job["company_name"],
            "status": job["status"],
            "created_at": job["created_at"],
            "started_at": job.get("started_at"),
        }

    return job


@router.get(
    "/graph/{company_name}",
    response_model=EntityGraphResponse,
    summary="Get entity graph",
    description=(
        "Retrieve the entity relationship graph for a company. "
        "Returns cached result if already built, or 404 if not yet built. "
        "Call POST /entities/build-graph/{company_name} first to trigger a build."
    ),
)
async def get_graph(
    company_name: str,
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the most recently built entity graph for a company.

    Args:
        company_name: Company name to retrieve graph for

    Returns:
        Full EntityGraphResponse or 404 if not built yet
    """
    clean_name = company_name.strip()

    # Find the most recent completed job for this company
    completed_jobs = [
        job for job in _build_jobs.values()
        if job["company_name"].lower() == clean_name.lower()
        and job["status"] == "completed"
        and job.get("result")
    ]

    if not completed_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No completed graph found for '{clean_name}'. "
                f"Call POST /api/v1/entities/build-graph/{company_name} to build one."
            ),
        )

    # Return most recent completed result
    latest_job = sorted(completed_jobs, key=lambda j: j.get("completed_at", ""), reverse=True)[0]
    result = latest_job["result"]

    # Map result dict back to response model
    return EntityGraphResponse(
        root_company=result["root_company"],
        built_at=result["built_at"],
        sources_used=result["sources_used"],
        overall_fraud_score=result["overall_fraud_score"],
        risk_level=result["risk_level"],
        entity_count=result["entity_count"],
        relationship_count=result["relationship_count"],
        fraud_signal_count=result["fraud_signal_count"],
        entities=[EntityNode(**e) for e in result["entities"]],
        relationships=[RelationshipEdge(**r) for r in result["relationships"]],
        fraud_signals=[FraudSignalSchema(**s) for s in result["fraud_signals"]],
        errors=result.get("errors", []),
    )


@router.get(
    "/related/{assessment_id}",
    response_model=RelatedEntitiesResponse,
    summary="Get related entities for an assessment",
    description=(
        "Look up entity graph data linked to a specific assessment. "
        "Uses the assessment's insured_entity_name or insured_name to find "
        "a previously built graph and returns the key fraud signals."
    ),
)
async def get_related_entities(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get entity relationship context for an assessment.

    Finds the insured company from the assessment, looks up any previously
    built entity graph, and returns fraud signal summary.

    Args:
        assessment_id: UUID of the assessment
        current_user: Authenticated user
        db: Database session

    Returns:
        Related entity summary with key fraud signals
    """
    # Fetch assessment
    try:
        result = await db.execute(
            select(Assessment).where(Assessment.id == uuid.UUID(assessment_id))
        )
        assessment = result.scalar_one_or_none()
    except (ValueError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid assessment ID: {e}",
        )

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )

    # Permission check
    if assessment.created_by != current_user.id and current_user.role not in ("admin", "underwriter"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this assessment's entities",
        )

    company_name = assessment.insured_entity_name or assessment.insured_name or ""
    if not company_name:
        return RelatedEntitiesResponse(
            assessment_id=assessment_id,
            company_name="",
            graph_available=False,
            fraud_score=None,
            risk_level=None,
            key_signals=[],
            message="Assessment has no insured company name. Set insured_entity_name to build an entity graph.",
        )

    # Find completed graph job
    completed_jobs = [
        job for job in _build_jobs.values()
        if job["company_name"].lower() == company_name.lower()
        and job["status"] == "completed"
        and job.get("result")
    ]

    if not completed_jobs:
        return RelatedEntitiesResponse(
            assessment_id=assessment_id,
            company_name=company_name,
            graph_available=False,
            fraud_score=None,
            risk_level=None,
            key_signals=[],
            message=(
                f"No entity graph built for '{company_name}'. "
                f"Call POST /api/v1/entities/build-graph/{company_name} to build one."
            ),
        )

    latest_job = sorted(completed_jobs, key=lambda j: j.get("completed_at", ""), reverse=True)[0]
    result_data = latest_job["result"]

    # Return top fraud signals (highest severity first)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    signals = sorted(
        result_data.get("fraud_signals", []),
        key=lambda s: (severity_order.get(s.get("severity", "low"), 3), -s.get("confidence", 0)),
    )
    key_signals = signals[:5]  # Top 5 signals

    return RelatedEntitiesResponse(
        assessment_id=assessment_id,
        company_name=company_name,
        graph_available=True,
        fraud_score=result_data.get("overall_fraud_score"),
        risk_level=result_data.get("risk_level"),
        key_signals=key_signals,
        message=f"Entity graph available for '{company_name}' with {len(signals)} fraud signal(s).",
    )


@router.post(
    "/detect-fraud",
    response_model=FraudDetectionResponse,
    summary="Run fraud detection on multiple companies",
    description=(
        "Build entity graphs for up to 10 companies and run fraud detection algorithms. "
        "This is a synchronous endpoint that may take 30-90 seconds. "
        "For single companies, prefer POST /entities/build-graph/{company_name} "
        "(async with background processing)."
    ),
)
async def detect_fraud(
    request: FraudDetectionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Run fraud detection on a set of companies synchronously.

    Builds entity graphs for each company and aggregates fraud signals
    across the entire set to detect related-party fraud networks.

    Args:
        request: List of company names and depth
        current_user: Authenticated user

    Returns:
        Aggregated fraud detection results
    """
    if not request.company_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one company name is required",
        )

    results = []
    total_entities = 0
    total_relationships = 0
    total_signals = 0
    highest_score = 0
    highest_company = ""

    for company_name in request.company_names:
        clean_name = company_name.strip()
        if not clean_name:
            continue

        try:
            graph = await build_entity_graph(clean_name, depth=request.depth)
            graph_dict = entity_graph_to_dict(graph)

            total_entities += graph.entity_count if hasattr(graph, 'entity_count') else len(graph.entities)
            total_relationships += len(graph.relationships)
            total_signals += len(graph.fraud_signals)

            if graph.overall_fraud_score > highest_score:
                highest_score = graph.overall_fraud_score
                highest_company = clean_name

            # Top 3 signals per company
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            top_signals = sorted(
                graph.fraud_signals,
                key=lambda s: (severity_order.get(s.severity, 3), -s.confidence),
            )[:3]

            results.append({
                "company_name": clean_name,
                "fraud_score": graph.overall_fraud_score,
                "risk_level": graph.risk_level,
                "entity_count": len(graph.entities),
                "relationship_count": len(graph.relationships),
                "signal_count": len(graph.fraud_signals),
                "top_signals": [
                    {
                        "signal_type": s.signal_type,
                        "severity": s.severity,
                        "description": s.description,
                        "confidence": s.confidence,
                    }
                    for s in top_signals
                ],
                "sources_used": graph.sources_used,
            })

        except Exception as e:
            logger.error(f"Fraud detection failed for '{clean_name}': {e}")
            results.append({
                "company_name": clean_name,
                "error": str(e),
                "fraud_score": 0,
                "risk_level": "unknown",
            })

    if not results:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="All company lookups failed",
        )

    # Overall risk level based on highest score
    if highest_score >= 70:
        overall_risk = "critical"
    elif highest_score >= 45:
        overall_risk = "high"
    elif highest_score >= 20:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    return FraudDetectionResponse(
        companies_analysed=len(results),
        total_entities=total_entities,
        total_relationships=total_relationships,
        total_signals=total_signals,
        highest_risk_company=highest_company,
        highest_fraud_score=highest_score,
        overall_risk_level=overall_risk,
        results=results,
    )


@router.get(
    "/jobs",
    summary="List all graph build jobs",
    description="List all entity graph build jobs (admin/debugging use).",
)
async def list_jobs(
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    List recent graph build jobs.

    Args:
        limit: Maximum number of jobs to return
        current_user: Authenticated user

    Returns:
        List of job summaries
    """
    jobs = list(_build_jobs.values())
    # Sort newest first
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    jobs = jobs[:limit]

    # Strip large result payload from listing
    return [
        {
            "job_id": j["job_id"],
            "company_name": j["company_name"],
            "status": j["status"],
            "created_at": j.get("created_at"),
            "completed_at": j.get("completed_at"),
            "fraud_score": j.get("fraud_score"),
            "risk_level": j.get("risk_level"),
            "error": j.get("error"),
        }
        for j in jobs
    ]
