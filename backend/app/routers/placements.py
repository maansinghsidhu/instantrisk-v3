"""
InstantRisk V3 - Placements Router

API endpoints for managing Lloyd's subscription market placements.
Handles the full placement lifecycle from creation through binding.

Key concepts:
- Placement: The overall risk being placed across multiple syndicates
- Lead syndicate: The first syndicate to quote, sets terms and conditions
- Lines: Individual syndicate participations in a placement
- Signing schedule: Final adjustment of lines to reach target percentage
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.lloyds import (
    PlacementCreate,
    PlacementResponse,
    SyndicateLineRequest,
    SyndicateLineResponse,
    SigningSchedule,
)
from app.services.subscription_service import SubscriptionWorkflowService

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class PlacementListResponse(BaseModel):
    """Response for listing placements."""
    placements: List[PlacementResponse]
    total: int


class LineStatusUpdate(BaseModel):
    """Request to update a line's status."""
    status: str = Field(
        ...,
        description="New status: quoted, written, signed, declined, scratched"
    )


class SigningScheduleResponse(BaseModel):
    """Response for signing schedule calculation."""
    placement_id: int
    umr: str
    total_written_line: float
    target_line: float
    signing_percentage: float
    lines: List[dict]
    signing_date: Optional[datetime] = None


# =============================================================================
# Helper Functions
# =============================================================================

def _placement_to_response(placement) -> PlacementResponse:
    """Convert placement model to response schema."""
    lines = []
    for line in placement.lines:
        lines.append(SyndicateLineResponse(
            id=line.id,
            syndicate_number=line.syndicate_number or "",
            syndicate_name=line.syndicate_name,
            written_line=line.line_percentage,
            signed_line=line.signed_line,
            order_percentage=line.order_percentage,
            status=line.status,
            conditions=line.conditions,
            subjectivities=line.subjectivities or [],
            quoted_at=line.quoted_at,
            written_at=line.written_at,
            signed_at=line.signed_at,
        ))

    return PlacementResponse(
        id=placement.id,
        umr=placement.umr,
        lead_syndicate_id=placement.lead_syndicate_id,
        lead_underwriter_name=placement.lead_underwriter_name,
        total_line=placement.total_line or Decimal("0"),
        target_line=placement.target_line or Decimal("100"),
        minimum_lead_line=placement.minimum_lead_line or Decimal("25"),
        status=placement.status,
        gross_premium=placement.gross_premium or Decimal("0"),
        currency=placement.currency or "GBP",
        inception_date=placement.inception_date,
        expiry_date=placement.expiry_date,
        created_at=placement.created_at,
        placed_at=placement.placed_at,
        lines=lines,
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/", response_model=PlacementResponse, status_code=status.HTTP_201_CREATED)
async def create_placement(
    request: PlacementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlacementResponse:
    """
    Create a new subscription market placement.

    Creates a placement record for a risk identified by UMR, specifying
    the lead syndicate and initial placement parameters.

    Args:
        request: PlacementCreate with UMR, lead syndicate, and details.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        PlacementResponse with created placement details.

    Raises:
        HTTPException: If UMR not found or lead syndicate invalid.
    """
    service = SubscriptionWorkflowService(db)

    try:
        placement = await service.create_placement(
            umr=request.umr,
            lead_syndicate_id=request.lead_syndicate,
            details={
                "lead_underwriter_name": request.lead_underwriter,
                "gross_premium": request.gross_premium,
                "currency": request.currency,
                "target_line": request.target_line,
                "minimum_lead_line": request.minimum_lead_line,
                "quote_deadline": request.quote_deadline,
                "inception_date": request.inception_date,
                "expiry_date": request.expiry_date,
                "created_by_id": current_user.id,
                "created_by_type": "user",
            }
        )
        await db.commit()

        # Reload with relationships
        placement = await service.get_placement(placement.id)
        return _placement_to_response(placement)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=PlacementListResponse)
async def list_placements(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    syndicate_id: Optional[int] = Query(None, description="Filter by syndicate"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlacementListResponse:
    """
    List placements with optional filtering.

    Returns placements accessible to the current user. Non-admin users
    only see placements for their syndicate.

    Args:
        status_filter: Optional filter by placement status.
        syndicate_id: Optional filter by syndicate ID.
        limit: Maximum number of results.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        PlacementListResponse with list of placements.
    """
    service = SubscriptionWorkflowService(db)

    # Non-admin users can only see their syndicate's placements
    effective_syndicate_id = syndicate_id
    if current_user.role.value != "admin" and current_user.syndicate_id:
        effective_syndicate_id = current_user.syndicate_id

    try:
        placements = await service.list_placements(
            status=status_filter,
            syndicate_id=effective_syndicate_id,
            limit=limit,
        )

        placement_responses = [_placement_to_response(p) for p in placements]

        return PlacementListResponse(
            placements=placement_responses,
            total=len(placement_responses),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{placement_id}", response_model=PlacementResponse)
async def get_placement(
    placement_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlacementResponse:
    """
    Get placement details by ID.

    Returns full placement details including all syndicate lines
    and activity history.

    Args:
        placement_id: The placement ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        PlacementResponse with full placement details.

    Raises:
        HTTPException: If placement not found or access denied.
    """
    service = SubscriptionWorkflowService(db)
    placement = await service.get_placement(placement_id)

    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement {placement_id} not found"
        )

    # Check access for non-admin users
    if current_user.role.value != "admin" and current_user.syndicate_id:
        # User can see if their syndicate is lead or has a line
        has_access = (
            placement.lead_syndicate_id == current_user.syndicate_id or
            any(line.syndicate_id == current_user.syndicate_id for line in placement.lines)
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this placement"
            )

    return _placement_to_response(placement)


@router.get("/umr/{umr}", response_model=PlacementResponse)
async def get_placement_by_umr(
    umr: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlacementResponse:
    """
    Get placement by Unique Market Reference (UMR).

    Retrieves placement using the Lloyd's UMR identifier.

    Args:
        umr: The Unique Market Reference.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        PlacementResponse with placement details.

    Raises:
        HTTPException: If placement not found or access denied.
    """
    service = SubscriptionWorkflowService(db)
    placement = await service.get_placement_by_umr(umr)

    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement with UMR {umr} not found"
        )

    # Check access for non-admin users
    if current_user.role.value != "admin" and current_user.syndicate_id:
        has_access = (
            placement.lead_syndicate_id == current_user.syndicate_id or
            any(line.syndicate_id == current_user.syndicate_id for line in placement.lines)
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this placement"
            )

    return _placement_to_response(placement)


@router.post("/{placement_id}/lines", response_model=SyndicateLineResponse, status_code=status.HTTP_201_CREATED)
async def add_syndicate_line(
    placement_id: int,
    request: SyndicateLineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyndicateLineResponse:
    """
    Add a syndicate line to a placement.

    Adds a new follower line from a syndicate to an existing placement.
    The syndicate must not already have a line on this placement.

    Args:
        placement_id: The placement ID.
        request: SyndicateLineRequest with line details.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        SyndicateLineResponse with created line details.

    Raises:
        HTTPException: If placement not found, syndicate invalid, or duplicate line.
    """
    service = SubscriptionWorkflowService(db)

    # Verify placement exists
    placement = await service.get_placement(placement_id)
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement {placement_id} not found"
        )

    # Get syndicate ID from syndicate number
    from sqlalchemy import select
    from app.models.syndicate import Syndicate

    syndicate_result = await db.execute(
        select(Syndicate).where(Syndicate.aiin == request.syndicate_number)
    )
    syndicate = syndicate_result.scalar_one_or_none()

    if not syndicate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Syndicate {request.syndicate_number} not found"
        )

    try:
        line = await service.add_follower_line(
            placement_id=placement_id,
            syndicate_id=syndicate.id,
            line_percentage=float(request.written_line),
            conditions=request.conditions,
        )

        # Update subjectivities if provided
        if request.subjectivities:
            line.subjectivities = request.subjectivities
            await db.flush()

        await db.commit()

        return SyndicateLineResponse(
            id=line.id,
            syndicate_number=line.syndicate_number or "",
            syndicate_name=line.syndicate_name,
            written_line=line.line_percentage,
            signed_line=line.signed_line,
            order_percentage=line.order_percentage,
            status=line.status,
            conditions=line.conditions,
            subjectivities=line.subjectivities or [],
            quoted_at=line.quoted_at,
            written_at=line.written_at,
            signed_at=line.signed_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{placement_id}/lines/{line_id}/status", response_model=SyndicateLineResponse)
async def update_line_status(
    placement_id: int,
    line_id: int,
    request: LineStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyndicateLineResponse:
    """
    Update the status of a syndicate line.

    Updates a line's status through the placement workflow
    (quoted -> written -> signed, or declined/scratched).

    Args:
        placement_id: The placement ID.
        line_id: The line ID to update.
        request: LineStatusUpdate with new status.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        SyndicateLineResponse with updated line details.

    Raises:
        HTTPException: If line not found or invalid status.
    """
    service = SubscriptionWorkflowService(db)

    # Verify placement exists
    placement = await service.get_placement(placement_id)
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement {placement_id} not found"
        )

    # Verify line belongs to placement
    line = None
    for l in placement.lines:
        if l.id == line_id:
            line = l
            break

    if not line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line {line_id} not found on placement {placement_id}"
        )

    # Check user has permission (syndicate user can only update own lines)
    if current_user.role.value != "admin":
        if current_user.syndicate_id != line.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own syndicate's lines"
            )

    try:
        updated_line = await service.update_line_status(line_id, request.status)
        await db.commit()

        return SyndicateLineResponse(
            id=updated_line.id,
            syndicate_number=updated_line.syndicate_number or "",
            syndicate_name=updated_line.syndicate_name,
            written_line=updated_line.line_percentage,
            signed_line=updated_line.signed_line,
            order_percentage=updated_line.order_percentage,
            status=updated_line.status,
            conditions=updated_line.conditions,
            subjectivities=updated_line.subjectivities or [],
            quoted_at=updated_line.quoted_at,
            written_at=updated_line.written_at,
            signed_at=updated_line.signed_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{placement_id}/signing-schedule", response_model=SigningScheduleResponse)
async def calculate_signing_schedule(
    placement_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SigningScheduleResponse:
    """
    Calculate the signing schedule for a placement.

    Calculates how lines will be adjusted to reach the target
    percentage (typically 100%) when the placement is signed.

    Args:
        placement_id: The placement ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        SigningScheduleResponse with calculated signed lines.

    Raises:
        HTTPException: If placement not found.
    """
    service = SubscriptionWorkflowService(db)

    placement = await service.get_placement(placement_id)
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement {placement_id} not found"
        )

    try:
        schedule_data = await service.calculate_signed_lines(placement_id)

        return SigningScheduleResponse(
            placement_id=schedule_data["placement_id"],
            umr=schedule_data["umr"],
            total_written_line=schedule_data["total_written"],
            target_line=schedule_data["target_line"],
            signing_percentage=schedule_data["signing_percentage"],
            lines=schedule_data["lines"],
            signing_date=None,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{placement_id}/signing-schedule", response_model=SigningScheduleResponse)
async def generate_signing_schedule(
    placement_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SigningScheduleResponse:
    """
    Generate and save the signing schedule for a placement.

    Calculates the signed lines and saves them to the database.
    This represents the official signing of the placement.

    Args:
        placement_id: The placement ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        SigningScheduleResponse with finalized signed lines.

    Raises:
        HTTPException: If placement not found or no active lines.
    """
    service = SubscriptionWorkflowService(db)

    placement = await service.get_placement(placement_id)
    if not placement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Placement {placement_id} not found"
        )

    # Authorization: Only admin or lead syndicate can generate signing schedule
    if current_user.role.value != "admin":
        if current_user.syndicate_id != placement.lead_syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin or lead syndicate can generate signing schedule"
            )

    try:
        schedule = await service.generate_signing_schedule(placement_id)

        # Get updated placement for response
        signing_data = await service.calculate_signed_lines(placement_id)

        # Update placement status to bound
        await service.update_placement_status(placement_id, "bound")

        await db.commit()

        return SigningScheduleResponse(
            placement_id=signing_data["placement_id"],
            umr=signing_data["umr"],
            total_written_line=signing_data["total_written"],
            target_line=signing_data["target_line"],
            signing_percentage=signing_data["signing_percentage"],
            lines=schedule,
            signing_date=datetime.now(timezone.utc),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
