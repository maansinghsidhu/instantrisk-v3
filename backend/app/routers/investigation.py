"""
InstantRisk V2 - Autonomous Investigation Router

Endpoints for triggering and monitoring autonomous company investigations.
Uses LangGraph multi-agent system to investigate companies in 3 minutes.
"""

import logging
import uuid
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.services.autonomous_investigator import run_autonomous_investigation

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

class InvestigationTriggerResponse(BaseModel):
    """Response when investigation is triggered."""
    job_id: str
    assessment_id: str
    company_name: str
    status: str
    message: str


class InvestigationStatusResponse(BaseModel):
    """Response for investigation status check."""
    job_id: str
    assessment_id: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    errors: list[str]


class InvestigationReportResponse(BaseModel):
    """Response containing full investigation report."""
    assessment_id: str
    company_name: str
    report: dict
    generated_at: str
    overall_risk_score: int
    recommendation: str


# =============================================================================
# Background Task
# =============================================================================

async def run_investigation_task(
    assessment_id: str,
    company_name: str,
    companies_house_number: Optional[str],
    db: AsyncSession
):
    """
    Background task to run investigation and store results in database.

    Args:
        assessment_id: Assessment UUID
        company_name: Company to investigate
        companies_house_number: Optional UK registration number
        db: Database session
    """
    try:
        logger.info(f"Background investigation started for assessment {assessment_id}")

        # Update assessment status
        result = await db.execute(
            select(Assessment).where(Assessment.id == uuid.UUID(assessment_id))
        )
        assessment = result.scalar_one_or_none()

        if not assessment:
            logger.error(f"Assessment {assessment_id} not found")
            return

        # Set investigation status
        assessment.investigation_status = "in_progress"
        await db.commit()

        # Run autonomous investigation
        investigation_result = await run_autonomous_investigation(
            company_name=company_name,
            assessment_id=assessment_id,
            companies_house_number=companies_house_number
        )

        # Store results in assessment
        assessment.investigation_report = investigation_result.get("final_report", {})
        assessment.investigation_status = investigation_result.get("status", "failed")

        # Update risk score if not already set
        if assessment.risk_score is None:
            overall_score = investigation_result.get("final_report", {}).get("overall_risk_score", 50)
            assessment.risk_score = overall_score

        await db.commit()

        logger.info(f"Investigation completed for assessment {assessment_id}: {investigation_result.get('status')}")

    except Exception as e:
        logger.error(f"Investigation task failed for {assessment_id}: {e}")

        # Update status to failed
        try:
            result = await db.execute(
                select(Assessment).where(Assessment.id == uuid.UUID(assessment_id))
            )
            assessment = result.scalar_one_or_none()
            if assessment:
                assessment.investigation_status = "failed"
                assessment.investigation_report = {"error": str(e)}
                await db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update investigation status: {db_error}")


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/run/{assessment_id}",
    response_model=InvestigationTriggerResponse,
    summary="Trigger autonomous investigation",
    description="Start autonomous investigation for a company (3-minute process)"
)
async def trigger_investigation(
    assessment_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger autonomous investigation for an assessment.

    The investigation runs in the background and results are stored in the assessment.

    Args:
        assessment_id: UUID of the assessment to investigate
        background_tasks: FastAPI background tasks
        current_user: Authenticated user
        db: Database session

    Returns:
        Job status and tracking information
    """
    try:
        # Validate assessment exists and user has access
        result = await db.execute(
            select(Assessment).where(Assessment.id == uuid.UUID(assessment_id))
        )
        assessment = result.scalar_one_or_none()

        if not assessment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assessment not found"
            )

        # Check user permissions (must be owner or admin)
        if assessment.created_by != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to investigate this assessment"
            )

        # Check if investigation already in progress
        if assessment.investigation_status == "in_progress":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Investigation already in progress"
            )

        # Determine company name
        company_name = assessment.insured_entity_name or assessment.insured_name

        if not company_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assessment must have insured_entity_name or insured_name to investigate"
            )

        # Generate job ID
        job_id = f"inv-{uuid.uuid4().hex[:12]}"

        # Trigger background investigation
        background_tasks.add_task(
            run_investigation_task,
            assessment_id=str(assessment.id),
            company_name=company_name,
            companies_house_number=assessment.companies_house_number,
            db=db
        )

        return InvestigationTriggerResponse(
            job_id=job_id,
            assessment_id=str(assessment.id),
            company_name=company_name,
            status="started",
            message="Investigation started. This will take approximately 3 minutes."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger investigation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger investigation: {str(e)}"
        )


@router.get(
    "/status/{assessment_id}",
    response_model=InvestigationStatusResponse,
    summary="Check investigation status",
    description="Get current status of autonomous investigation"
)
async def get_investigation_status(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check the status of an autonomous investigation.

    Args:
        assessment_id: UUID of the assessment
        current_user: Authenticated user
        db: Database session

    Returns:
        Current investigation status
    """
    try:
        # Fetch assessment
        result = await db.execute(
            select(Assessment).where(Assessment.id == uuid.UUID(assessment_id))
        )
        assessment = result.scalar_one_or_none()

        if not assessment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assessment not found"
            )

        # Check permissions
        if assessment.created_by != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this investigation"
            )

        # Extract status from investigation_report if available
        investigation_report = assessment.investigation_report or {}
        status_value = assessment.investigation_status or "not_started"

        return InvestigationStatusResponse(
            job_id=f"inv-{str(assessment.id)[:12]}",
            assessment_id=str(assessment.id),
            status=status_value,
            started_at=investigation_report.get("started_at"),
            completed_at=investigation_report.get("completed_at"),
            errors=investigation_report.get("errors", [])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get investigation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get investigation status: {str(e)}"
        )


@router.get(
    "/report/{assessment_id}",
    response_model=InvestigationReportResponse,
    summary="Get investigation report",
    description="Retrieve full investigation report for an assessment"
)
async def get_investigation_report(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the full investigation report for an assessment.

    Args:
        assessment_id: UUID of the assessment
        current_user: Authenticated user
        db: Database session

    Returns:
        Complete investigation report
    """
    try:
        # Fetch assessment
        result = await db.execute(
            select(Assessment).where(Assessment.id == uuid.UUID(assessment_id))
        )
        assessment = result.scalar_one_or_none()

        if not assessment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assessment not found"
            )

        # Check permissions
        if assessment.created_by != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this investigation"
            )

        # Check if investigation exists
        investigation_report = assessment.investigation_report

        if not investigation_report or not investigation_report.get("report_text"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No investigation report available. Run investigation first."
            )

        company_name = assessment.insured_entity_name or assessment.insured_name or "Unknown"

        return InvestigationReportResponse(
            assessment_id=str(assessment.id),
            company_name=company_name,
            report=investigation_report,
            generated_at=investigation_report.get("generated_at", ""),
            overall_risk_score=investigation_report.get("overall_risk_score", 0),
            recommendation=investigation_report.get("recommendation", "REFER")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get investigation report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get investigation report: {str(e)}"
        )
