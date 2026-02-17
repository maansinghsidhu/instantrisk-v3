"""
Global Event Intelligence Router

API endpoints for the 24/7 global event monitoring system.
Sources: GDELT, USGS, NOAA, NASA FIRMS, CISA.

Endpoints:
  GET  /api/v1/events/recent          - last 24h global events
  GET  /api/v1/events/portfolio-impact - events affecting portfolio
  POST /api/v1/events/manual-check     - trigger an immediate check
  GET  /api/v1/events/scheduler-status - APScheduler health
  GET  /api/v1/events/{event_id}       - single event detail
"""

from typing import Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.global_event import GlobalEvent
from app.services.event_monitor import (
    get_recent_events,
    get_portfolio_impact_summary,
    run_event_monitoring,
)
from app.tasks.scheduled_jobs import get_scheduler_info, get_job_status

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class GlobalEventResponse(BaseModel):
    """Single global event."""
    id: int
    event_type: str
    source: str
    title: str
    description: Optional[str]
    severity: str
    location: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    affected_region: Optional[str]
    event_time: datetime
    created_at: datetime
    is_processed: bool
    affected_assessment_count: int

    class Config:
        from_attributes = True


class RecentEventsResponse(BaseModel):
    """Paginated list of recent global events."""
    period_hours: int
    total: int
    events: list[GlobalEventResponse]


class PortfolioImpactResponse(BaseModel):
    """Summary of portfolio impact from recent global events."""
    period_hours: int
    impactful_events_count: int
    total_assessments_affected: int
    severity_breakdown: dict[str, int]
    source_breakdown: dict[str, int]
    event_type_breakdown: dict[str, int]
    top_events: list[dict[str, Any]]


class ManualCheckResponse(BaseModel):
    """Result from a manual event check trigger."""
    message: str
    job_id: str


class SchedulerStatusResponse(BaseModel):
    """APScheduler health and job info."""
    running: bool
    jobs: list[dict[str, Any]]
    job_statuses: dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/recent",
    response_model=RecentEventsResponse,
    summary="Get recent global events (last 24h)",
    description=(
        "Returns global events from GDELT, USGS, NOAA, NASA FIRMS, and CISA "
        "detected in the last N hours (default 24). "
        "Filter by event_type (earthquake, hurricane, wildfire, cyber_alert, geopolitical) "
        "or severity (low, medium, high, critical)."
    ),
)
async def get_recent_global_events(
    hours: int = Query(24, ge=1, le=168, description="Look-back window in hours (max 7 days)"),
    event_type: Optional[str] = Query(
        None,
        description="Filter: earthquake | hurricane | wildfire | cyber_alert | geopolitical | flood | tornado",
    ),
    severity: Optional[str] = Query(
        None,
        description="Filter: low | medium | high | critical",
    ),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of events to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve recent global events from the monitoring database.

    The scheduler fetches from all sources every hour.
    Use POST /manual-check to trigger an immediate refresh.
    """
    events = await get_recent_events(
        db=db,
        hours=hours,
        event_type=event_type,
        severity=severity,
        limit=limit,
    )

    return RecentEventsResponse(
        period_hours=hours,
        total=len(events),
        events=[GlobalEventResponse.model_validate(e) for e in events],
    )


@router.get(
    "/portfolio-impact",
    response_model=PortfolioImpactResponse,
    summary="Get events affecting the portfolio",
    description=(
        "Returns a summary of global events from the last N hours that "
        "have been matched to one or more assessments in the portfolio. "
        "Shows severity breakdown, source breakdown, and top impactful events."
    ),
)
async def get_portfolio_impact(
    hours: int = Query(24, ge=1, le=168, description="Look-back window in hours"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Portfolio impact analysis from recent global events.

    An event is considered 'impactful' if the location/event-type matched
    at least one active assessment during the last monitoring run.
    """
    summary = await get_portfolio_impact_summary(db=db, hours=hours)
    return PortfolioImpactResponse(**summary)


@router.post(
    "/manual-check",
    response_model=ManualCheckResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an immediate global event check",
    description=(
        "Fires an immediate event monitoring run outside the normal hourly schedule. "
        "The job runs in the background - poll GET /scheduler-status for results."
    ),
)
async def trigger_manual_check(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger an immediate event monitoring run.

    The job is queued as a FastAPI BackgroundTask and runs asynchronously.
    Returns immediately with a 202 Accepted so the caller is not blocked.
    """
    async def _run_job():
        try:
            result = await run_event_monitoring()
            import logging
            logging.getLogger("instantrisk.event_monitor").info(
                "Manual check complete: %s", result
            )
        except Exception as exc:
            import logging
            logging.getLogger("instantrisk.event_monitor").error(
                "Manual check failed: %s", exc, exc_info=True
            )

    background_tasks.add_task(_run_job)

    return ManualCheckResponse(
        message=(
            "Event monitoring job queued. "
            "Check GET /api/v1/events/recent in ~60 seconds for new results."
        ),
        job_id="manual_check",
    )


@router.get(
    "/scheduler-status",
    response_model=SchedulerStatusResponse,
    summary="Get APScheduler status",
    description="Returns whether the background scheduler is running and the last known result for each job.",
)
async def get_scheduler_status(
    current_user: User = Depends(get_current_user),
):
    """
    APScheduler health check.

    Shows:
    - Whether the scheduler is running
    - Registered jobs and their next scheduled run time
    - Last known success/error status per job
    """
    info = get_scheduler_info()
    return SchedulerStatusResponse(
        running=info["running"],
        jobs=info["jobs"],
        job_statuses=info["job_statuses"],
    )


@router.get(
    "/{event_id}",
    response_model=GlobalEventResponse,
    summary="Get a single global event by ID",
)
async def get_event_detail(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the full details of a single global event including raw_data payload
    from the original source API.
    """
    event = await db.get(GlobalEvent, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Global event {event_id} not found",
        )
    return GlobalEventResponse.model_validate(event)
