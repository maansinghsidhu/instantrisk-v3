"""
InstantRisk V3 - UMR Router

API endpoints for managing Lloyd's Unique Market References (UMRs).
Provides UMR generation, validation, and lookup services.

UMR Format: B0999ABCDEF001
- B0999: Broker code (assigned by Lloyd's)
- 26: Year (last 2 digits)
- XXXXXX: Sequence number (alphanumeric)
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.lloyds import UMRCreate, UMRResponse
from app.services.umr_service import UMRService

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class UMRGenerateRequest(BaseModel):
    """Request to generate a new UMR."""
    broker_pin: Optional[str] = Field(
        None,
        description="Lloyd's broker PIN (e.g., 'B0999'). Defaults to system broker."
    )
    year_of_account: Optional[str] = Field(
        None,
        description="Year of account (YOA) - 2-digit year. Defaults to current."
    )
    assessment_id: Optional[str] = Field(
        None,
        description="Optional assessment ID to link"
    )
    class_of_business: Optional[str] = Field(
        None,
        description="Lloyd's class of business code"
    )
    risk_type: Optional[str] = Field(
        None,
        description="Type of risk being placed"
    )


class UMRGenerateResponse(BaseModel):
    """Response for UMR generation."""
    umr: str
    broker_pin: str
    year_of_account: str
    sequence: int
    status: str
    assessment_id: Optional[str]
    created_at: datetime


class UMRDetailsResponse(BaseModel):
    """Response for UMR details."""
    umr: str
    broker_code: str
    year: str
    sequence: int
    status: str
    assessment_id: Optional[str]
    risk_type: Optional[str]
    class_of_business: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


class UMRValidationResponse(BaseModel):
    """Response for UMR validation."""
    umr: str
    is_valid: bool
    broker_code: Optional[str]
    year: Optional[str]
    sequence: Optional[str]
    message: str


# =============================================================================
# Helper Functions
# =============================================================================

def _umr_to_response(umr_record) -> UMRDetailsResponse:
    """Convert UMR model to response schema."""
    return UMRDetailsResponse(
        umr=umr_record.umr,
        broker_code=umr_record.broker_code,
        year=umr_record.year,
        sequence=umr_record.sequence,
        status=umr_record.status,
        assessment_id=umr_record.assessment_id,
        risk_type=umr_record.risk_type,
        class_of_business=umr_record.class_of_business,
        created_at=umr_record.created_at,
        updated_at=umr_record.updated_at,
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/generate", response_model=UMRGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_umr(
    request: UMRGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UMRGenerateResponse:
    """
    Generate a new Unique Market Reference (UMR).

    Creates a new UMR following Lloyd's format standards. The UMR
    can optionally be linked to an assessment.

    Args:
        request: UMRGenerateRequest with optional broker PIN and parameters.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        UMRGenerateResponse with generated UMR details.

    Raises:
        HTTPException: If broker code format is invalid.
    """
    service = UMRService(db)

    try:
        umr = await service.generate_umr(
            broker_code=request.broker_pin,
            year=request.year_of_account,
            assessment_id=request.assessment_id,
            risk_type=request.risk_type,
            class_of_business=request.class_of_business,
        )
        await db.commit()

        # Get the full record
        umr_record = await service.get_umr(umr)

        return UMRGenerateResponse(
            umr=umr_record.umr,
            broker_pin=umr_record.broker_code,
            year_of_account=umr_record.year,
            sequence=umr_record.sequence,
            status=umr_record.status,
            assessment_id=umr_record.assessment_id,
            created_at=umr_record.created_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{umr}", response_model=UMRDetailsResponse)
async def get_umr_details(
    umr: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UMRDetailsResponse:
    """
    Get UMR details by identifier.

    Retrieves the full details of a UMR including its status,
    linked assessment, and metadata.

    Args:
        umr: The Unique Market Reference.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        UMRDetailsResponse with UMR details.

    Raises:
        HTTPException: If UMR not found.
    """
    service = UMRService(db)
    umr_record = await service.get_umr(umr)

    if not umr_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UMR {umr} not found"
        )

    return _umr_to_response(umr_record)


@router.get("/validate/{umr}", response_model=UMRValidationResponse)
async def validate_umr(
    umr: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UMRValidationResponse:
    """
    Validate UMR format.

    Checks if a UMR follows the correct Lloyd's format and parses
    its component parts.

    Args:
        umr: The Unique Market Reference to validate.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        UMRValidationResponse with validation result.
    """
    service = UMRService(db)

    is_valid = service.validate_umr(umr)

    if is_valid:
        components = service.parse_umr(umr)
        return UMRValidationResponse(
            umr=umr,
            is_valid=True,
            broker_code=components.broker_code if components else None,
            year=components.year if components else None,
            sequence=components.sequence if components else None,
            message="UMR format is valid",
        )
    else:
        return UMRValidationResponse(
            umr=umr,
            is_valid=False,
            broker_code=None,
            year=None,
            sequence=None,
            message="Invalid UMR format. Expected format: B followed by 4 digits, then 6-10 alphanumeric characters (e.g., B099926ABC001)",
        )


@router.get("/assessment/{assessment_id}", response_model=UMRDetailsResponse)
async def get_umr_for_assessment(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UMRDetailsResponse:
    """
    Get UMR linked to an assessment.

    Retrieves the UMR associated with a specific assessment.

    Args:
        assessment_id: The assessment ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        UMRDetailsResponse with UMR details.

    Raises:
        HTTPException: If no UMR found for assessment.
    """
    service = UMRService(db)
    umr_record = await service.get_umr_by_assessment(assessment_id)

    if not umr_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No UMR found for assessment {assessment_id}"
        )

    return _umr_to_response(umr_record)
