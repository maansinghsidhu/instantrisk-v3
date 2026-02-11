"""
InstantRisk V3 - Compliance Router

API endpoints for regulatory compliance automation.
Handles Lloyd's and Solvency II reporting requirements.

Key submissions:
- PMDR: Premium and Claims Market Data Returns
- RDS: Realistic Disaster Scenarios
- QRT: Solvency II Quantitative Reporting Templates
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
    PMDRRequest,
    PMDRResponse,
    RDSScenario,
    RDSResponse,
    ComplianceSubmissionStatus,
)
from app.services.compliance_engine import ComplianceAutomationEngine

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class RDSRequest(BaseModel):
    """Request to calculate RDS scenarios."""
    period: Optional[str] = Field(None, description="Reporting period (defaults to current year)")
    scenarios: Optional[List[str]] = Field(None, description="Specific scenarios to calculate (or all)")


class QRTRequest(BaseModel):
    """Request to generate Solvency II QRT."""
    period: str = Field(..., description="Reporting period (e.g., '2026-Q1')")
    templates: Optional[List[str]] = Field(
        None,
        description="Specific QRT templates to generate (or all)"
    )


class QRTResponse(BaseModel):
    """Response for QRT generation."""
    period: str
    syndicate_id: int
    templates: Dict[str, Any]
    generated_at: datetime
    status: str


class SubmissionListResponse(BaseModel):
    """Response for listing submissions."""
    submissions: List[ComplianceSubmissionStatus]
    total: int


class ValidationResult(BaseModel):
    """Single validation result."""
    rule_code: str
    field: str
    severity: str
    message: str


class ValidationResponse(BaseModel):
    """Response for submission validation."""
    submission_id: int
    is_valid: bool
    errors: List[ValidationResult]
    warnings: List[ValidationResult]
    validated_at: datetime


class SubmitResponse(BaseModel):
    """Response for regulator submission."""
    submitted: bool
    submission_reference: str
    submitted_at: datetime
    message: str


# =============================================================================
# Helper Functions
# =============================================================================

def _get_user_syndicate_id(current_user: User) -> int:
    """Get syndicate ID from user, raising error if not found."""
    if current_user.role.value == "admin":
        # Admin must specify syndicate in request
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin users must specify syndicate_id in request"
        )
    if not current_user.syndicate_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be assigned to a syndicate"
        )
    return current_user.syndicate_id


def _submission_to_response(submission) -> ComplianceSubmissionStatus:
    """Convert submission model to response schema."""
    return ComplianceSubmissionStatus(
        id=submission.id,
        submission_type=submission.submission_type,
        period=submission.period,
        status=submission.status,
        is_valid=submission.is_valid,
        validation_errors=submission.validation_errors or [],
        validation_warnings=submission.validation_warnings or [],
        submitted_at=submission.submitted_at,
        submission_reference=submission.submission_reference,
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/pmdr", response_model=PMDRResponse)
async def generate_pmdr(
    request: PMDRRequest,
    syndicate_id: Optional[int] = Query(None, description="Syndicate ID (required for admin users)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PMDRResponse:
    """
    Generate PMDR (Premium and Claims Market Data Return).

    Generates a PMDR submission with all required premium and claims
    data for the specified period.

    Args:
        request: PMDRRequest with period and optional class filters.
        syndicate_id: Syndicate ID (required for admin users).
        current_user: The authenticated user.
        db: Database session.

    Returns:
        PMDRResponse with complete PMDR data.
    """
    # Determine syndicate ID
    effective_syndicate_id = syndicate_id
    if current_user.role.value != "admin":
        effective_syndicate_id = current_user.syndicate_id

    if not effective_syndicate_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Syndicate ID is required"
        )

    engine = ComplianceAutomationEngine(db)

    report = await engine.generate_pmdr_return(
        syndicate_id=effective_syndicate_id,
        period=request.period,
        save=True,
    )
    await db.commit()

    # Convert by_class values to proper format
    by_class_formatted = {}
    for k, v in report.by_class.items():
        if isinstance(v, dict):
            by_class_formatted[k] = {
                key: str(val) if isinstance(val, Decimal) else val
                for key, val in v.items()
            }
        else:
            by_class_formatted[k] = v

    return PMDRResponse(
        period=report.period,
        syndicate_id=report.syndicate_id,
        gross_written_premium=report.gross_written_premium,
        net_written_premium=report.net_written_premium,
        gross_earned_premium=report.gross_earned_premium,
        net_earned_premium=report.net_earned_premium,
        gross_claims_paid=report.gross_claims_paid,
        net_claims_paid=report.net_claims_paid,
        gross_claims_outstanding=report.gross_claims_outstanding,
        net_claims_outstanding=report.net_claims_outstanding,
        reinsurance_premium_ceded=report.reinsurance_premium_ceded,
        reinsurance_recoveries=report.reinsurance_recoveries,
        by_class=by_class_formatted,
        by_year_of_account=report.by_year_of_account,
        validation_status="validated",
        generated_at=datetime.now(timezone.utc),
    )


@router.post("/rds", response_model=RDSResponse)
async def calculate_rds(
    request: RDSRequest,
    syndicate_id: Optional[int] = Query(None, description="Syndicate ID (required for admin users)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RDSResponse:
    """
    Calculate RDS (Realistic Disaster Scenarios).

    Runs all standard Lloyd's RDS scenarios and calculates
    gross and net losses for each.

    Args:
        request: RDSRequest with optional period and scenario filters.
        syndicate_id: Syndicate ID (required for admin users).
        current_user: The authenticated user.
        db: Database session.

    Returns:
        RDSResponse with all scenario results.
    """
    effective_syndicate_id = syndicate_id
    if current_user.role.value != "admin":
        effective_syndicate_id = current_user.syndicate_id

    if not effective_syndicate_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Syndicate ID is required"
        )

    engine = ComplianceAutomationEngine(db)

    report = await engine.calculate_rds(
        syndicate_id=effective_syndicate_id,
        period=request.period,
        save=True,
    )
    await db.commit()

    scenarios = [
        RDSScenario(
            scenario_id=s["scenario_id"],
            scenario_name=s["scenario_name"],
            scenario_type=s["scenario_type"],
            region=s["region"],
            gross_loss=Decimal(str(s["gross_loss"])),
            net_loss=Decimal(str(s["net_loss"])),
            policies_affected=s["policies_affected"],
        )
        for s in report.scenarios
    ]

    return RDSResponse(
        period=report.period,
        syndicate_id=report.syndicate_id,
        scenarios=scenarios,
        total_gross_loss=report.total_gross_loss,
        total_net_loss=report.total_net_loss,
        pml_100yr=report.pml_100yr,
        pml_250yr=report.pml_250yr,
        validation_status="validated",
        calculated_at=datetime.now(timezone.utc),
    )


@router.post("/qrt", response_model=QRTResponse)
async def generate_qrt(
    request: QRTRequest,
    syndicate_id: Optional[int] = Query(None, description="Syndicate ID (required for admin users)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QRTResponse:
    """
    Generate Solvency II QRT (Quantitative Reporting Templates).

    Generates the required Solvency II QRT templates for regulatory
    submission.

    Args:
        request: QRTRequest with period and optional template filters.
        syndicate_id: Syndicate ID (required for admin users).
        current_user: The authenticated user.
        db: Database session.

    Returns:
        QRTResponse with generated template data.
    """
    effective_syndicate_id = syndicate_id
    if current_user.role.value != "admin":
        effective_syndicate_id = current_user.syndicate_id

    if not effective_syndicate_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Syndicate ID is required"
        )

    engine = ComplianceAutomationEngine(db)

    qrt_data = await engine.generate_solvency_qrt(
        syndicate_id=effective_syndicate_id,
        period=request.period,
        templates=request.templates,
        save=True,
    )
    await db.commit()

    return QRTResponse(
        period=request.period,
        syndicate_id=effective_syndicate_id,
        templates=qrt_data,
        generated_at=datetime.now(timezone.utc),
        status="generated",
    )


@router.get("/submissions", response_model=SubmissionListResponse)
async def list_submissions(
    syndicate_id: Optional[int] = Query(None, description="Syndicate ID filter"),
    submission_type: Optional[str] = Query(None, description="Submission type filter"),
    status_filter: Optional[str] = Query(None, alias="status", description="Status filter"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionListResponse:
    """
    List compliance submissions.

    Returns submissions for the user's syndicate (or all for admin users).

    Args:
        syndicate_id: Optional filter by syndicate ID.
        submission_type: Optional filter by type (PMDR, RDS, QRT).
        status_filter: Optional filter by status.
        limit: Maximum results.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        SubmissionListResponse with list of submissions.
    """
    effective_syndicate_id = syndicate_id
    if current_user.role.value != "admin":
        effective_syndicate_id = current_user.syndicate_id

    if not effective_syndicate_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Syndicate ID is required"
        )

    engine = ComplianceAutomationEngine(db)

    submissions = await engine.list_submissions(
        syndicate_id=effective_syndicate_id,
        submission_type=submission_type,
        status=status_filter,
        limit=limit,
    )

    submission_list = [_submission_to_response(s) for s in submissions]

    return SubmissionListResponse(
        submissions=submission_list,
        total=len(submission_list),
    )


@router.get("/submissions/{submission_id}", response_model=ComplianceSubmissionStatus)
async def get_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComplianceSubmissionStatus:
    """
    Get a compliance submission by ID.

    Args:
        submission_id: The submission ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        ComplianceSubmissionStatus with submission details.

    Raises:
        HTTPException: If submission not found or access denied.
    """
    engine = ComplianceAutomationEngine(db)
    submission = await engine.get_submission(submission_id)

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found"
        )

    # Check access
    if current_user.role.value != "admin":
        if current_user.syndicate_id != submission.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this submission"
            )

    return _submission_to_response(submission)


@router.post("/submissions/{submission_id}/validate", response_model=ValidationResponse)
async def validate_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationResponse:
    """
    Validate a compliance submission.

    Runs validation rules against the submission data and returns
    any errors or warnings.

    Args:
        submission_id: The submission ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        ValidationResponse with validation results.

    Raises:
        HTTPException: If submission not found.
    """
    engine = ComplianceAutomationEngine(db)
    submission = await engine.get_submission(submission_id)

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found"
        )

    # Check access
    if current_user.role.value != "admin":
        if current_user.syndicate_id != submission.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this submission"
            )

    # Run validation
    validation_results = await engine.validate_submission(
        submission.submission_type,
        submission.data,
    )

    errors = [
        ValidationResult(
            rule_code=v.rule_code,
            field=v.field,
            severity=v.severity.value,
            message=v.message,
        )
        for v in validation_results
        if v.severity.value == "error"
    ]

    warnings = [
        ValidationResult(
            rule_code=v.rule_code,
            field=v.field,
            severity=v.severity.value,
            message=v.message,
        )
        for v in validation_results
        if v.severity.value == "warning"
    ]

    is_valid = len(errors) == 0

    # Update submission validation status
    submission.is_valid = is_valid
    submission.validation_errors = [{"code": e.rule_code, "field": e.field, "message": e.message} for e in errors]
    submission.validation_warnings = [{"code": w.rule_code, "field": w.field, "message": w.message} for w in warnings]
    submission.status = "validated" if is_valid else "draft"
    submission.validated_at = datetime.now(timezone.utc)

    await db.commit()

    return ValidationResponse(
        submission_id=submission_id,
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        validated_at=datetime.now(timezone.utc),
    )


@router.post("/submissions/{submission_id}/submit", response_model=SubmitResponse)
async def submit_to_regulator(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmitResponse:
    """
    Submit a validated submission to Lloyd's/regulator.

    Marks the submission as submitted and generates a submission reference.
    In production, this would integrate with Lloyd's reporting systems.

    Args:
        submission_id: The submission ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        SubmitResponse with submission reference.

    Raises:
        HTTPException: If submission not found, not valid, or already submitted.
    """
    engine = ComplianceAutomationEngine(db)
    submission = await engine.get_submission(submission_id)

    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found"
        )

    # Check access
    if current_user.role.value != "admin":
        if current_user.syndicate_id != submission.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this submission"
            )

    # Check if already submitted
    if submission.status == "submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission has already been submitted"
        )

    try:
        result = await engine.submit_to_regulator(submission_id)
        await db.commit()

        return SubmitResponse(
            submitted=result["submitted"],
            submission_reference=result["submission_reference"],
            submitted_at=datetime.fromisoformat(result["submitted_at"]),
            message=f"Submission {submission_id} submitted successfully",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
