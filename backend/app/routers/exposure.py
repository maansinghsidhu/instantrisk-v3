"""
InstantRisk V3 - Exposure Router

API endpoints for portfolio exposure monitoring and management.
Provides real-time exposure tracking, capacity alerts, and PML calculations.

Key features:
- Exposure aggregation by zone, peril, and class of business
- Event accumulation analysis for catastrophe scenarios
- Capacity limit monitoring and alerts
- Probable Maximum Loss (PML) calculations
- Historical trend analysis
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.lloyds import (
    ExposureByZone,
    ExposureByPeril,
    ExposureDashboard,
    EventAccumulationRequest,
    EventAccumulationResponse,
)
from app.services.exposure_service import ExposureMonitoringService
from app.models.exposure_loss import ExposureLoss, ExposureClaim, LossType, ClaimStatus
from sqlalchemy import select, func

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class ExposureZoneResponse(BaseModel):
    """Response for exposure by zone."""
    syndicate_id: int
    as_of: datetime
    by_zone: List[ExposureByZone]
    total_exposure: float


class ExposurePerilResponse(BaseModel):
    """Response for exposure by peril."""
    syndicate_id: int
    as_of: datetime
    by_peril: List[ExposureByPeril]
    total_exposure: float


class ExposureClassResponse(BaseModel):
    """Response for exposure by class of business."""
    syndicate_id: int
    as_of: datetime
    by_class: Dict[str, float]
    total_exposure: float


class CapacityAlert(BaseModel):
    """Capacity alert details."""
    alert_type: str
    severity: str
    dimension: str
    key: str
    current_exposure: float
    limit: float
    utilization_pct: float
    message: str


class CapacityAlertsResponse(BaseModel):
    """Response for capacity alerts."""
    syndicate_id: int
    alerts: List[CapacityAlert]
    checked_at: datetime


class PMLResponse(BaseModel):
    """Response for PML calculation."""
    syndicate_id: int
    return_period: int
    gross_pml: float
    net_pml: float
    by_zone: Dict[str, float]
    by_peril: Dict[str, float]
    confidence_level: float
    calculation_date: datetime


class TrendDataPoint(BaseModel):
    """Single trend data point."""
    date: str
    gross_exposure: float
    net_exposure: float
    policy_count: int
    change_pct: Optional[float] = None


class ExposureTrendResponse(BaseModel):
    """Response for exposure trend."""
    syndicate_id: int
    days: int
    trend_data: List[TrendDataPoint]


class SnapshotResponse(BaseModel):
    """Response for snapshot recording."""
    syndicate_id: int
    recorded_at: datetime
    message: str


# =============================================================================
# Helper Functions
# =============================================================================

def _check_syndicate_access(current_user: User, syndicate_id: int) -> None:
    """Check if user has access to syndicate data."""
    if current_user.role.value != "admin":
        if current_user.syndicate_id != syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this syndicate's data"
            )


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/zones/{syndicate_id}", response_model=ExposureZoneResponse)
async def get_exposure_by_zone(
    syndicate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExposureZoneResponse:
    """
    Get exposure aggregated by geographic zone.

    Returns exposure data grouped by geographic zones (NA, EU, APAC, etc.)
    for portfolio monitoring and capacity management.

    Args:
        syndicate_id: The syndicate ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        ExposureZoneResponse with exposure by zone.
    """
    _check_syndicate_access(current_user, syndicate_id)

    service = ExposureMonitoringService(db)
    exposure_by_zone = await service.calculate_exposure_by_zone(syndicate_id)

    zones = []
    total = Decimal("0")

    for zone, exposure in exposure_by_zone.items():
        total += exposure
        zones.append(ExposureByZone(
            zone=zone,
            gross_exposure=exposure,
            net_exposure=exposure,  # Simplified - gross = net without RI
            policy_count=0,  # Would come from detailed query
            utilization_percentage=None,
        ))

    return ExposureZoneResponse(
        syndicate_id=syndicate_id,
        as_of=datetime.now(timezone.utc),
        by_zone=zones,
        total_exposure=float(total),
    )


@router.get("/perils/{syndicate_id}", response_model=ExposurePerilResponse)
async def get_exposure_by_peril(
    syndicate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExposurePerilResponse:
    """
    Get exposure aggregated by peril type.

    Returns exposure data grouped by peril types (windstorm, earthquake,
    cyber, etc.) for risk concentration analysis.

    Args:
        syndicate_id: The syndicate ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        ExposurePerilResponse with exposure by peril.
    """
    _check_syndicate_access(current_user, syndicate_id)

    service = ExposureMonitoringService(db)
    exposure_by_peril = await service.calculate_exposure_by_peril(syndicate_id)

    perils = []
    total = Decimal("0")

    for peril, exposure in exposure_by_peril.items():
        total += exposure
        perils.append(ExposureByPeril(
            peril=peril,
            gross_exposure=exposure,
            net_exposure=exposure,
            pml_100yr=None,
            pml_250yr=None,
        ))

    return ExposurePerilResponse(
        syndicate_id=syndicate_id,
        as_of=datetime.now(timezone.utc),
        by_peril=perils,
        total_exposure=float(total),
    )


@router.get("/classes/{syndicate_id}", response_model=ExposureClassResponse)
async def get_exposure_by_class(
    syndicate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExposureClassResponse:
    """
    Get exposure aggregated by class of business.

    Returns exposure data grouped by Lloyd's class of business codes
    for portfolio composition analysis.

    Args:
        syndicate_id: The syndicate ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        ExposureClassResponse with exposure by class.
    """
    _check_syndicate_access(current_user, syndicate_id)

    service = ExposureMonitoringService(db)
    exposure_by_class = await service.calculate_exposure_by_class(syndicate_id)

    by_class = {k: float(v) for k, v in exposure_by_class.items()}
    total = sum(by_class.values())

    return ExposureClassResponse(
        syndicate_id=syndicate_id,
        as_of=datetime.now(timezone.utc),
        by_class=by_class,
        total_exposure=total,
    )


@router.get("/dashboard/{syndicate_id}", response_model=ExposureDashboard)
async def get_exposure_dashboard(
    syndicate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExposureDashboard:
    """
    Get full exposure dashboard data.

    Returns comprehensive exposure data including breakdowns by zone,
    peril, and capacity alerts for dashboard visualization.

    Args:
        syndicate_id: The syndicate ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        ExposureDashboard with complete exposure data.
    """
    _check_syndicate_access(current_user, syndicate_id)

    service = ExposureMonitoringService(db)

    # Get all exposure data
    exposure_by_zone = await service.calculate_exposure_by_zone(syndicate_id)
    exposure_by_peril = await service.calculate_exposure_by_peril(syndicate_id)
    alerts = await service.check_capacity_limits(syndicate_id)

    # Calculate totals
    total_gross = sum(exposure_by_zone.values())
    total_net = total_gross  # Simplified

    # Get syndicate capacity
    from sqlalchemy import select
    from app.models.syndicate import Syndicate

    syndicate_result = await db.execute(
        select(Syndicate).where(Syndicate.id == syndicate_id)
    )
    syndicate = syndicate_result.scalar_one_or_none()
    capacity = Decimal(str(syndicate.capacity)) if syndicate and syndicate.capacity else None

    # Calculate utilization
    utilization = Decimal("0")
    if capacity and capacity > 0:
        utilization = (total_net / capacity) * 100

    # Build zone list
    zones = []
    for zone, exposure in exposure_by_zone.items():
        zones.append(ExposureByZone(
            zone=zone,
            gross_exposure=exposure,
            net_exposure=exposure,
            policy_count=0,
            utilization_percentage=None,
        ))

    # Build peril list
    perils = []
    for peril, exposure in exposure_by_peril.items():
        perils.append(ExposureByPeril(
            peril=peril,
            gross_exposure=exposure,
            net_exposure=exposure,
            pml_100yr=None,
            pml_250yr=None,
        ))

    # Build alert messages
    alert_messages = [a.message for a in alerts]

    return ExposureDashboard(
        syndicate_id=syndicate_id,
        as_of=datetime.now(timezone.utc),
        total_gross_exposure=total_gross,
        total_net_exposure=total_net,
        capacity=capacity,
        utilization_percentage=utilization,
        by_zone=zones,
        by_peril=perils,
        alerts=alert_messages,
    )


@router.post("/event-accumulation", response_model=EventAccumulationResponse)
async def run_event_accumulation(
    request: EventAccumulationRequest,
    syndicate_id: int = Query(..., description="Syndicate ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventAccumulationResponse:
    """
    Run event accumulation analysis.

    Calculates total exposure for a defined catastrophe event scenario
    based on geographic footprint and peril type.

    Args:
        request: EventAccumulationRequest with event definition.
        syndicate_id: The syndicate ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        EventAccumulationResponse with accumulation results.
    """
    _check_syndicate_access(current_user, syndicate_id)

    service = ExposureMonitoringService(db)

    event_definition = {
        "event_type": request.event_type,
        "event_name": request.event_name,
        "region": request.affected_region,
        **request.parameters,
    }

    result = await service.run_event_accumulation(syndicate_id, event_definition)
    await db.commit()

    return EventAccumulationResponse(
        event_id=result["event_id"],
        event_name=result["event_name"],
        event_type=result["event_type"],
        region=result["region"],
        gross_exposure=Decimal(str(result["gross_exposure"])),
        net_exposure=Decimal(str(result["net_exposure"])),
        policies_affected=result["policies_affected"],
        calculated_at=datetime.now(timezone.utc),
    )


@router.get("/alerts/{syndicate_id}", response_model=CapacityAlertsResponse)
async def get_capacity_alerts(
    syndicate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CapacityAlertsResponse:
    """
    Get capacity limit alerts for a syndicate.

    Checks current exposure against defined limits and returns
    any warnings or breaches.

    Args:
        syndicate_id: The syndicate ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        CapacityAlertsResponse with list of alerts.
    """
    _check_syndicate_access(current_user, syndicate_id)

    service = ExposureMonitoringService(db)
    alerts = await service.check_capacity_limits(syndicate_id)

    alert_list = [
        CapacityAlert(
            alert_type=a.alert_type,
            severity=a.severity.value,
            dimension=a.dimension,
            key=a.key,
            current_exposure=float(a.current_exposure),
            limit=float(a.limit),
            utilization_pct=a.utilization_pct,
            message=a.message,
        )
        for a in alerts
    ]

    return CapacityAlertsResponse(
        syndicate_id=syndicate_id,
        alerts=alert_list,
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/pml/{syndicate_id}", response_model=PMLResponse)
async def calculate_pml(
    syndicate_id: int,
    return_period: int = Query(100, description="Return period in years (e.g., 100, 250)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PMLResponse:
    """
    Calculate Probable Maximum Loss (PML).

    Calculates PML for a specified return period using stored exposure
    data and standard actuarial techniques.

    Args:
        syndicate_id: The syndicate ID.
        return_period: Return period in years (default 100).
        current_user: The authenticated user.
        db: Database session.

    Returns:
        PMLResponse with PML calculation results.
    """
    _check_syndicate_access(current_user, syndicate_id)

    service = ExposureMonitoringService(db)
    pml_result = await service.calculate_pml(syndicate_id, return_period)

    return PMLResponse(
        syndicate_id=syndicate_id,
        return_period=pml_result["return_period"],
        gross_pml=pml_result["gross_pml"],
        net_pml=pml_result["net_pml"],
        by_zone=pml_result["by_zone"],
        by_peril=pml_result["by_peril"],
        confidence_level=pml_result["confidence_level"],
        calculation_date=datetime.fromisoformat(pml_result["calculation_date"].replace("Z", "+00:00"))
            if isinstance(pml_result["calculation_date"], str)
            else pml_result["calculation_date"],
    )


@router.get("/trend/{syndicate_id}", response_model=ExposureTrendResponse)
async def get_exposure_trend(
    syndicate_id: int,
    days: int = Query(30, ge=7, le=365, description="Number of days of history"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExposureTrendResponse:
    """
    Get historical exposure trend data.

    Returns daily exposure totals for trend analysis and
    visualization over the specified period.

    Args:
        syndicate_id: The syndicate ID.
        days: Number of days of history (default 30).
        current_user: The authenticated user.
        db: Database session.

    Returns:
        ExposureTrendResponse with trend data.
    """
    _check_syndicate_access(current_user, syndicate_id)

    service = ExposureMonitoringService(db)
    trend_data = await service.get_exposure_trend(syndicate_id, days)

    data_points = [
        TrendDataPoint(
            date=point["date"] or "",
            gross_exposure=point["gross_exposure"],
            net_exposure=point["net_exposure"],
            policy_count=point["policy_count"],
            change_pct=point.get("change_pct"),
        )
        for point in trend_data
    ]

    return ExposureTrendResponse(
        syndicate_id=syndicate_id,
        days=days,
        trend_data=data_points,
    )


@router.post("/snapshot/{syndicate_id}", response_model=SnapshotResponse)
async def record_exposure_snapshot(
    syndicate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SnapshotResponse:
    """
    Record a point-in-time exposure snapshot.

    Creates a snapshot of current exposure data for historical
    tracking and trend analysis.

    Args:
        syndicate_id: The syndicate ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        SnapshotResponse confirming the snapshot was recorded.
    """
    _check_syndicate_access(current_user, syndicate_id)

    service = ExposureMonitoringService(db)
    await service.record_snapshot(syndicate_id)
    await service.update_aggregates(syndicate_id)
    await db.commit()

    return SnapshotResponse(
        syndicate_id=syndicate_id,
        recorded_at=datetime.now(timezone.utc),
        message="Exposure snapshot recorded successfully",
    )


# =============================================================================
# Loss and Claims Schemas
# =============================================================================

class LossCreate(BaseModel):
    """Schema for creating a new loss."""
    assessment_id: Optional[str] = None
    loss_date: datetime
    loss_amount: float
    currency: str = "GBP"
    loss_type: str = "attritional"
    territory: Optional[str] = None
    peril: Optional[str] = None
    class_of_business: Optional[str] = None
    description: Optional[str] = None
    reference_number: Optional[str] = None


class LossResponse(BaseModel):
    """Response for a loss record."""
    id: int
    assessment_id: Optional[str]
    syndicate_id: int
    loss_date: datetime
    loss_amount: float
    currency: str
    loss_type: str
    territory: Optional[str]
    peril: Optional[str]
    class_of_business: Optional[str]
    description: Optional[str]
    reference_number: Optional[str]
    created_at: datetime


class ClaimCreate(BaseModel):
    """Schema for creating a new claim."""
    assessment_id: Optional[str] = None
    claim_number: str
    claim_date: datetime
    claim_amount: float
    reserve_amount: float = 0
    currency: str = "GBP"
    status: str = "reported"
    cause: Optional[str] = None
    territory: Optional[str] = None
    peril: Optional[str] = None
    class_of_business: Optional[str] = None
    description: Optional[str] = None
    claimant_name: Optional[str] = None


class ClaimResponse(BaseModel):
    """Response for a claim record."""
    id: int
    assessment_id: Optional[str]
    syndicate_id: int
    claim_number: str
    claim_date: datetime
    claim_amount: float
    reserve_amount: float
    paid_amount: float
    currency: str
    status: str
    cause: Optional[str]
    territory: Optional[str]
    peril: Optional[str]
    class_of_business: Optional[str]
    description: Optional[str]
    claimant_name: Optional[str]
    created_at: datetime


class LossRatioResponse(BaseModel):
    """Response for loss ratio calculation."""
    syndicate_id: int
    period_start: datetime
    period_end: datetime
    earned_premium: float
    incurred_losses: float
    loss_ratio: float
    by_territory: Dict[str, float]
    by_peril: Dict[str, float]


class ActualStatsResponse(BaseModel):
    """Response for actual exposure stats."""
    syndicate_id: int
    total_incurred_losses: float
    total_claims_amount: float
    total_reserves: float
    total_paid: float
    loss_ratio: float
    claims_count: int
    open_claims_count: int
    losses_by_territory: Dict[str, float]
    losses_by_peril: Dict[str, float]
    recent_losses: List[LossResponse]
    recent_claims: List[ClaimResponse]


# =============================================================================
# Loss and Claims Endpoints
# =============================================================================

@router.get("/losses/{syndicate_id}", response_model=List[LossResponse])
async def get_losses(
    syndicate_id: int,
    assessment_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[LossResponse]:
    """
    Get losses for a syndicate, optionally filtered by assessment.
    """
    _check_syndicate_access(current_user, syndicate_id)

    query = select(ExposureLoss).where(ExposureLoss.syndicate_id == syndicate_id)
    if assessment_id:
        query = query.where(ExposureLoss.assessment_id == assessment_id)
    query = query.order_by(ExposureLoss.loss_date.desc())

    result = await db.execute(query)
    losses = result.scalars().all()

    return [
        LossResponse(
            id=loss.id,
            assessment_id=loss.assessment_id,
            syndicate_id=loss.syndicate_id,
            loss_date=loss.loss_date,
            loss_amount=float(loss.loss_amount),
            currency=loss.currency,
            loss_type=loss.loss_type.value if loss.loss_type else "attritional",
            territory=loss.territory,
            peril=loss.peril,
            class_of_business=loss.class_of_business,
            description=loss.description,
            reference_number=loss.reference_number,
            created_at=loss.created_at,
        )
        for loss in losses
    ]


@router.post("/losses/{syndicate_id}", response_model=LossResponse)
async def create_loss(
    syndicate_id: int,
    loss_data: LossCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LossResponse:
    """
    Create a new loss record for a syndicate.
    """
    _check_syndicate_access(current_user, syndicate_id)

    loss = ExposureLoss(
        syndicate_id=syndicate_id,
        assessment_id=loss_data.assessment_id,
        loss_date=loss_data.loss_date,
        loss_amount=Decimal(str(loss_data.loss_amount)),
        currency=loss_data.currency,
        loss_type=LossType(loss_data.loss_type) if loss_data.loss_type else LossType.ATTRITIONAL,
        territory=loss_data.territory,
        peril=loss_data.peril,
        class_of_business=loss_data.class_of_business,
        description=loss_data.description,
        reference_number=loss_data.reference_number,
        created_by=current_user.id,
    )

    db.add(loss)
    await db.commit()
    await db.refresh(loss)

    return LossResponse(
        id=loss.id,
        assessment_id=loss.assessment_id,
        syndicate_id=loss.syndicate_id,
        loss_date=loss.loss_date,
        loss_amount=float(loss.loss_amount),
        currency=loss.currency,
        loss_type=loss.loss_type.value,
        territory=loss.territory,
        peril=loss.peril,
        class_of_business=loss.class_of_business,
        description=loss.description,
        reference_number=loss.reference_number,
        created_at=loss.created_at,
    )


@router.put("/losses/{loss_id}", response_model=LossResponse)
async def update_loss(
    loss_id: int,
    loss_data: LossCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LossResponse:
    """
    Update an existing loss record.
    """
    result = await db.execute(select(ExposureLoss).where(ExposureLoss.id == loss_id))
    loss = result.scalar_one_or_none()

    if not loss:
        raise HTTPException(status_code=404, detail="Loss not found")

    _check_syndicate_access(current_user, loss.syndicate_id)

    loss.assessment_id = loss_data.assessment_id
    loss.loss_date = loss_data.loss_date
    loss.loss_amount = Decimal(str(loss_data.loss_amount))
    loss.currency = loss_data.currency
    loss.loss_type = LossType(loss_data.loss_type) if loss_data.loss_type else LossType.ATTRITIONAL
    loss.territory = loss_data.territory
    loss.peril = loss_data.peril
    loss.class_of_business = loss_data.class_of_business
    loss.description = loss_data.description
    loss.reference_number = loss_data.reference_number

    await db.commit()
    await db.refresh(loss)

    return LossResponse(
        id=loss.id,
        assessment_id=loss.assessment_id,
        syndicate_id=loss.syndicate_id,
        loss_date=loss.loss_date,
        loss_amount=float(loss.loss_amount),
        currency=loss.currency,
        loss_type=loss.loss_type.value,
        territory=loss.territory,
        peril=loss.peril,
        class_of_business=loss.class_of_business,
        description=loss.description,
        reference_number=loss.reference_number,
        created_at=loss.created_at,
    )


@router.delete("/losses/{loss_id}")
async def delete_loss(
    loss_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a loss record.
    """
    result = await db.execute(select(ExposureLoss).where(ExposureLoss.id == loss_id))
    loss = result.scalar_one_or_none()

    if not loss:
        raise HTTPException(status_code=404, detail="Loss not found")

    _check_syndicate_access(current_user, loss.syndicate_id)

    await db.delete(loss)
    await db.commit()

    return {"message": "Loss deleted successfully"}


@router.get("/claims/{syndicate_id}", response_model=List[ClaimResponse])
async def get_claims(
    syndicate_id: int,
    assessment_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ClaimResponse]:
    """
    Get claims for a syndicate, optionally filtered by assessment or status.
    """
    _check_syndicate_access(current_user, syndicate_id)

    query = select(ExposureClaim).where(ExposureClaim.syndicate_id == syndicate_id)
    if assessment_id:
        query = query.where(ExposureClaim.assessment_id == assessment_id)
    if status:
        query = query.where(ExposureClaim.status == ClaimStatus(status))
    query = query.order_by(ExposureClaim.claim_date.desc())

    result = await db.execute(query)
    claims = result.scalars().all()

    return [
        ClaimResponse(
            id=claim.id,
            assessment_id=claim.assessment_id,
            syndicate_id=claim.syndicate_id,
            claim_number=claim.claim_number,
            claim_date=claim.claim_date,
            claim_amount=float(claim.claim_amount),
            reserve_amount=float(claim.reserve_amount) if claim.reserve_amount else 0,
            paid_amount=float(claim.paid_amount) if claim.paid_amount else 0,
            currency=claim.currency,
            status=claim.status.value if claim.status else "reported",
            cause=claim.cause,
            territory=claim.territory,
            peril=claim.peril,
            class_of_business=claim.class_of_business,
            description=claim.description,
            claimant_name=claim.claimant_name,
            created_at=claim.created_at,
        )
        for claim in claims
    ]


@router.post("/claims/{syndicate_id}", response_model=ClaimResponse)
async def create_claim(
    syndicate_id: int,
    claim_data: ClaimCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """
    Create a new claim record for a syndicate.
    """
    _check_syndicate_access(current_user, syndicate_id)

    claim = ExposureClaim(
        syndicate_id=syndicate_id,
        assessment_id=claim_data.assessment_id,
        claim_number=claim_data.claim_number,
        claim_date=claim_data.claim_date,
        claim_amount=Decimal(str(claim_data.claim_amount)),
        reserve_amount=Decimal(str(claim_data.reserve_amount)),
        currency=claim_data.currency,
        status=ClaimStatus(claim_data.status) if claim_data.status else ClaimStatus.REPORTED,
        cause=claim_data.cause,
        territory=claim_data.territory,
        peril=claim_data.peril,
        class_of_business=claim_data.class_of_business,
        description=claim_data.description,
        claimant_name=claim_data.claimant_name,
        created_by=current_user.id,
    )

    db.add(claim)
    await db.commit()
    await db.refresh(claim)

    return ClaimResponse(
        id=claim.id,
        assessment_id=claim.assessment_id,
        syndicate_id=claim.syndicate_id,
        claim_number=claim.claim_number,
        claim_date=claim.claim_date,
        claim_amount=float(claim.claim_amount),
        reserve_amount=float(claim.reserve_amount) if claim.reserve_amount else 0,
        paid_amount=float(claim.paid_amount) if claim.paid_amount else 0,
        currency=claim.currency,
        status=claim.status.value,
        cause=claim.cause,
        territory=claim.territory,
        peril=claim.peril,
        class_of_business=claim.class_of_business,
        description=claim.description,
        claimant_name=claim.claimant_name,
        created_at=claim.created_at,
    )


@router.put("/claims/{claim_id}", response_model=ClaimResponse)
async def update_claim(
    claim_id: int,
    claim_data: ClaimCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """
    Update an existing claim record.
    """
    result = await db.execute(select(ExposureClaim).where(ExposureClaim.id == claim_id))
    claim = result.scalar_one_or_none()

    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    _check_syndicate_access(current_user, claim.syndicate_id)

    claim.assessment_id = claim_data.assessment_id
    claim.claim_date = claim_data.claim_date
    claim.claim_amount = Decimal(str(claim_data.claim_amount))
    claim.reserve_amount = Decimal(str(claim_data.reserve_amount))
    claim.currency = claim_data.currency
    claim.status = ClaimStatus(claim_data.status) if claim_data.status else ClaimStatus.REPORTED
    claim.cause = claim_data.cause
    claim.territory = claim_data.territory
    claim.peril = claim_data.peril
    claim.class_of_business = claim_data.class_of_business
    claim.description = claim_data.description
    claim.claimant_name = claim_data.claimant_name

    await db.commit()
    await db.refresh(claim)

    return ClaimResponse(
        id=claim.id,
        assessment_id=claim.assessment_id,
        syndicate_id=claim.syndicate_id,
        claim_number=claim.claim_number,
        claim_date=claim.claim_date,
        claim_amount=float(claim.claim_amount),
        reserve_amount=float(claim.reserve_amount) if claim.reserve_amount else 0,
        paid_amount=float(claim.paid_amount) if claim.paid_amount else 0,
        currency=claim.currency,
        status=claim.status.value,
        cause=claim.cause,
        territory=claim.territory,
        peril=claim.peril,
        class_of_business=claim.class_of_business,
        description=claim.description,
        claimant_name=claim.claimant_name,
        created_at=claim.created_at,
    )


@router.get("/loss-ratio/{syndicate_id}", response_model=LossRatioResponse)
async def get_loss_ratio(
    syndicate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LossRatioResponse:
    """
    Calculate loss ratio for a syndicate based on actual losses and premium.
    """
    _check_syndicate_access(current_user, syndicate_id)

    # Get total incurred losses
    loss_result = await db.execute(
        select(func.sum(ExposureLoss.loss_amount))
        .where(ExposureLoss.syndicate_id == syndicate_id)
    )
    total_losses = float(loss_result.scalar() or 0)

    # Get losses by territory
    territory_result = await db.execute(
        select(ExposureLoss.territory, func.sum(ExposureLoss.loss_amount))
        .where(ExposureLoss.syndicate_id == syndicate_id)
        .where(ExposureLoss.territory.isnot(None))
        .group_by(ExposureLoss.territory)
    )
    losses_by_territory = {row[0]: float(row[1]) for row in territory_result.fetchall()}

    # Get losses by peril
    peril_result = await db.execute(
        select(ExposureLoss.peril, func.sum(ExposureLoss.loss_amount))
        .where(ExposureLoss.syndicate_id == syndicate_id)
        .where(ExposureLoss.peril.isnot(None))
        .group_by(ExposureLoss.peril)
    )
    losses_by_peril = {row[0]: float(row[1]) for row in peril_result.fetchall()}

    # Get syndicate premium (earned premium from assessments)
    from app.models.assessment import Assessment
    premium_result = await db.execute(
        select(func.sum(Assessment.premium))
        .where(Assessment.syndicate_id == syndicate_id)
        .where(Assessment.premium.isnot(None))
    )
    earned_premium = float(premium_result.scalar() or 0)

    # Calculate loss ratio
    loss_ratio = (total_losses / earned_premium * 100) if earned_premium > 0 else 0

    return LossRatioResponse(
        syndicate_id=syndicate_id,
        period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        period_end=datetime.now(timezone.utc),
        earned_premium=earned_premium,
        incurred_losses=total_losses,
        loss_ratio=round(loss_ratio, 2),
        by_territory=losses_by_territory,
        by_peril=losses_by_peril,
    )


@router.get("/actual-stats/{syndicate_id}", response_model=ActualStatsResponse)
async def get_actual_stats(
    syndicate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActualStatsResponse:
    """
    Get actual exposure stats including losses, claims, and ratios.
    """
    _check_syndicate_access(current_user, syndicate_id)

    # Get total losses
    loss_result = await db.execute(
        select(func.sum(ExposureLoss.loss_amount))
        .where(ExposureLoss.syndicate_id == syndicate_id)
    )
    total_losses = float(loss_result.scalar() or 0)

    # Get claims stats
    claims_result = await db.execute(
        select(
            func.sum(ExposureClaim.claim_amount),
            func.sum(ExposureClaim.reserve_amount),
            func.sum(ExposureClaim.paid_amount),
            func.count(ExposureClaim.id)
        )
        .where(ExposureClaim.syndicate_id == syndicate_id)
    )
    claims_row = claims_result.fetchone()
    total_claims = float(claims_row[0] or 0)
    total_reserves = float(claims_row[1] or 0)
    total_paid = float(claims_row[2] or 0)
    claims_count = int(claims_row[3] or 0)

    # Get open claims count
    open_claims_result = await db.execute(
        select(func.count(ExposureClaim.id))
        .where(ExposureClaim.syndicate_id == syndicate_id)
        .where(ExposureClaim.status.in_([ClaimStatus.REPORTED, ClaimStatus.OPEN, ClaimStatus.UNDER_REVIEW]))
    )
    open_claims_count = int(open_claims_result.scalar() or 0)

    # Get losses by territory
    territory_result = await db.execute(
        select(ExposureLoss.territory, func.sum(ExposureLoss.loss_amount))
        .where(ExposureLoss.syndicate_id == syndicate_id)
        .where(ExposureLoss.territory.isnot(None))
        .group_by(ExposureLoss.territory)
    )
    losses_by_territory = {row[0]: float(row[1]) for row in territory_result.fetchall()}

    # Get losses by peril
    peril_result = await db.execute(
        select(ExposureLoss.peril, func.sum(ExposureLoss.loss_amount))
        .where(ExposureLoss.syndicate_id == syndicate_id)
        .where(ExposureLoss.peril.isnot(None))
        .group_by(ExposureLoss.peril)
    )
    losses_by_peril = {row[0]: float(row[1]) for row in peril_result.fetchall()}

    # Get recent losses
    recent_losses_result = await db.execute(
        select(ExposureLoss)
        .where(ExposureLoss.syndicate_id == syndicate_id)
        .order_by(ExposureLoss.loss_date.desc())
        .limit(5)
    )
    recent_losses = [
        LossResponse(
            id=loss.id,
            assessment_id=loss.assessment_id,
            syndicate_id=loss.syndicate_id,
            loss_date=loss.loss_date,
            loss_amount=float(loss.loss_amount),
            currency=loss.currency,
            loss_type=loss.loss_type.value if loss.loss_type else "attritional",
            territory=loss.territory,
            peril=loss.peril,
            class_of_business=loss.class_of_business,
            description=loss.description,
            reference_number=loss.reference_number,
            created_at=loss.created_at,
        )
        for loss in recent_losses_result.scalars().all()
    ]

    # Get recent claims
    recent_claims_result = await db.execute(
        select(ExposureClaim)
        .where(ExposureClaim.syndicate_id == syndicate_id)
        .order_by(ExposureClaim.claim_date.desc())
        .limit(5)
    )
    recent_claims = [
        ClaimResponse(
            id=claim.id,
            assessment_id=claim.assessment_id,
            syndicate_id=claim.syndicate_id,
            claim_number=claim.claim_number,
            claim_date=claim.claim_date,
            claim_amount=float(claim.claim_amount),
            reserve_amount=float(claim.reserve_amount) if claim.reserve_amount else 0,
            paid_amount=float(claim.paid_amount) if claim.paid_amount else 0,
            currency=claim.currency,
            status=claim.status.value if claim.status else "reported",
            cause=claim.cause,
            territory=claim.territory,
            peril=claim.peril,
            class_of_business=claim.class_of_business,
            description=claim.description,
            claimant_name=claim.claimant_name,
            created_at=claim.created_at,
        )
        for claim in recent_claims_result.scalars().all()
    ]

    # Get earned premium for loss ratio
    from app.models.assessment import Assessment
    premium_result = await db.execute(
        select(func.sum(Assessment.premium))
        .where(Assessment.syndicate_id == syndicate_id)
        .where(Assessment.premium.isnot(None))
    )
    earned_premium = float(premium_result.scalar() or 0)
    loss_ratio = (total_losses / earned_premium * 100) if earned_premium > 0 else 0

    return ActualStatsResponse(
        syndicate_id=syndicate_id,
        total_incurred_losses=total_losses,
        total_claims_amount=total_claims,
        total_reserves=total_reserves,
        total_paid=total_paid,
        loss_ratio=round(loss_ratio, 2),
        claims_count=claims_count,
        open_claims_count=open_claims_count,
        losses_by_territory=losses_by_territory,
        losses_by_peril=losses_by_peril,
        recent_losses=recent_losses,
        recent_claims=recent_claims,
    )
