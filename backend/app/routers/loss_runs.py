"""
Loss Runs Router

API endpoints for uploading, parsing, and managing loss run documents.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from io import BytesIO

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    Query,
    status,
    BackgroundTasks,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.loss_run import InsuredLossRun, LossRunSummary, ClaimStatus
from app.models.user import User
from app.models.assessment import Assessment
from app.services.loss_run_parser import get_loss_run_parser, ParseResult
from app.services.s3_client import get_documents_client

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class ClaimResponse(BaseModel):
    """Single claim response."""
    id: str
    claim_number: Optional[str]
    claim_date: Optional[str]
    report_date: Optional[str]
    close_date: Optional[str]
    policy_year: Optional[int]
    claim_type: Optional[str]
    claim_description: Optional[str]
    claimant_name: Optional[str]
    status: Optional[str]
    amount_paid: float
    amount_reserved: float
    amount_incurred: float
    expense_paid: float
    expense_reserved: float
    parsing_confidence: Optional[float]
    row_number: Optional[int]

    class Config:
        from_attributes = True


class LossRunUploadResponse(BaseModel):
    """Response after uploading loss run file."""
    success: bool
    message: str
    file_id: str
    filename: str
    claims_parsed: int
    claims_failed: int
    overall_confidence: float
    warnings: List[str] = []
    errors: List[str] = []


class LossRunSummaryResponse(BaseModel):
    """Summary of loss run data for an assessment."""
    assessment_id: str
    total_claims: int
    open_claims: int
    closed_claims: int
    years_of_history: int
    total_paid: float
    total_reserved: float
    total_incurred: float
    average_severity: Optional[float]
    claim_frequency: Optional[float]
    largest_claim_amount: Optional[float]
    largest_claim_type: Optional[str]
    files_uploaded: int


class LossRunListResponse(BaseModel):
    """Paginated list of claims."""
    claims: List[ClaimResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# Helper functions
def validate_file_type(filename: str) -> str:
    """Validate and return file extension."""
    ext = filename.lower().split(".")[-1]
    allowed = ["pdf", "xlsx", "xls", "csv"]
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {ext}. Allowed types: {', '.join(allowed)}",
        )
    return ext


async def get_assessment_or_404(
    assessment_id: str,
    db: AsyncSession,
    user: User,
) -> Assessment:
    """Get assessment or raise 404."""
    try:
        # Validate UUID format
        uuid.UUID(str(assessment_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid assessment ID format",
        )

    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.created_by == user.id,
        )
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    return assessment


# Endpoints
@router.post(
    "/{assessment_id}/upload",
    response_model=LossRunUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_loss_run(
    assessment_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a loss run document for parsing.

    Accepts PDF, Excel (.xlsx, .xls), or CSV files up to 25MB.
    Files are parsed asynchronously and claims are extracted.
    """
    # Validate assessment ownership
    assessment = await get_assessment_or_404(assessment_id, db, current_user)

    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    validate_file_type(file.filename)

    # Check file size
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB",
        )

    # Check file count limit
    existing_count = await db.execute(
        select(func.count(InsuredLossRun.id.distinct())).where(
            InsuredLossRun.assessment_id == assessment_id
        )
    )
    # Note: This counts claims, not files. Could track files separately if needed.

    # Parse the file
    parser = get_loss_run_parser()
    file_obj = BytesIO(content)

    try:
        result: ParseResult = await parser.parse_file(
            file_obj=file_obj,
            filename=file.filename,
            assessment_id=assessment_id,
        )
    except Exception as e:
        logger.error(f"Loss run parsing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse file: {str(e)}",
        )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse file: {'; '.join(result.errors)}",
        )

    # Store parsed claims in database
    file_id = str(uuid.uuid4())
    s3_key = result.metadata.get("s3_key", "")

    claims_stored = 0
    for claim in result.claims:
        db_claim = InsuredLossRun(
            id=uuid.uuid4(),
            assessment_id=assessment_id,
            raw_file_path=s3_key,
            raw_filename=file.filename,
            claim_number=claim.claim_number,
            claim_date=claim.claim_date,
            report_date=claim.report_date,
            close_date=claim.close_date,
            policy_year=claim.policy_year,
            claim_type=claim.claim_type,
            claim_description=claim.claim_description,
            claimant_name=claim.claimant_name,
            status=ClaimStatus(claim.status) if claim.status in [s.value for s in ClaimStatus] else None,
            amount_paid=claim.amount_paid,
            amount_reserved=claim.amount_reserved,
            expense_paid=claim.expense_paid,
            expense_reserved=claim.expense_reserved,
            parsed_at=datetime.utcnow(),
            parsing_confidence=claim.parsing_confidence,
            parsing_notes=claim.parsing_notes,
            row_number=claim.row_number,
        )
        db.add(db_claim)
        claims_stored += 1

    await db.commit()

    # Index in Qdrant for RAG (background)
    background_tasks.add_task(
        index_loss_run_for_rag,
        assessment_id=assessment_id,
        filename=file.filename,
        claims=result.claims,
    )

    # Update summary (background)
    background_tasks.add_task(
        update_loss_run_summary,
        assessment_id=assessment_id,
    )

    logger.info(
        f"Uploaded loss run for assessment {assessment_id}: "
        f"{claims_stored} claims from {file.filename}"
    )

    return LossRunUploadResponse(
        success=True,
        message=f"Successfully parsed {claims_stored} claims",
        file_id=file_id,
        filename=file.filename,
        claims_parsed=claims_stored,
        claims_failed=result.error_rows,
        overall_confidence=result.overall_confidence,
        warnings=result.warnings,
        errors=result.errors,
    )


@router.get("/{assessment_id}", response_model=LossRunListResponse)
async def get_loss_runs(
    assessment_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None),
    year_filter: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get parsed loss run claims for an assessment.

    Supports filtering by status and policy year.
    """
    assessment = await get_assessment_or_404(assessment_id, db, current_user)

    # Build query
    query = select(InsuredLossRun).where(
        InsuredLossRun.assessment_id == assessment_id
    )

    if status_filter:
        query = query.where(InsuredLossRun.status == status_filter)
    if year_filter:
        query = query.where(InsuredLossRun.policy_year == year_filter)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(InsuredLossRun.claim_date.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    claims = result.scalars().all()

    return LossRunListResponse(
        claims=[
            ClaimResponse(
                id=str(c.id),
                claim_number=c.claim_number,
                claim_date=c.claim_date.isoformat() if c.claim_date else None,
                report_date=c.report_date.isoformat() if c.report_date else None,
                close_date=c.close_date.isoformat() if c.close_date else None,
                policy_year=c.policy_year,
                claim_type=c.claim_type,
                claim_description=c.claim_description,
                claimant_name=c.claimant_name,
                status=c.status.value if c.status else None,
                amount_paid=float(c.amount_paid or 0),
                amount_reserved=float(c.amount_reserved or 0),
                amount_incurred=float(c.total_incurred),
                expense_paid=float(c.expense_paid or 0),
                expense_reserved=float(c.expense_reserved or 0),
                parsing_confidence=c.parsing_confidence,
                row_number=c.row_number,
            )
            for c in claims
        ],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(claims)) < total,
    )


@router.get("/{assessment_id}/summary", response_model=LossRunSummaryResponse)
async def get_loss_run_summary(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated summary of loss run data."""
    assessment = await get_assessment_or_404(assessment_id, db, current_user)

    # Try to get cached summary
    result = await db.execute(
        select(LossRunSummary).where(LossRunSummary.assessment_id == assessment_id)
    )
    summary = result.scalar_one_or_none()

    if not summary:
        # Calculate on the fly
        claims_result = await db.execute(
            select(InsuredLossRun).where(InsuredLossRun.assessment_id == assessment_id)
        )
        claims = claims_result.scalars().all()

        if not claims:
            return LossRunSummaryResponse(
                assessment_id=assessment_id,
                total_claims=0,
                open_claims=0,
                closed_claims=0,
                years_of_history=0,
                total_paid=0,
                total_reserved=0,
                total_incurred=0,
                average_severity=None,
                claim_frequency=None,
                largest_claim_amount=None,
                largest_claim_type=None,
                files_uploaded=0,
            )

        total_paid = sum(float(c.amount_paid or 0) for c in claims)
        total_reserved = sum(float(c.amount_reserved or 0) for c in claims)
        open_claims = sum(1 for c in claims if c.status == ClaimStatus.OPEN)
        closed_claims = sum(1 for c in claims if c.status == ClaimStatus.CLOSED)

        years = set(c.policy_year for c in claims if c.policy_year)
        years_of_history = len(years) if years else 0

        largest = max(claims, key=lambda c: float(c.total_incurred), default=None)

        unique_files = set(c.raw_filename for c in claims if c.raw_filename)

        return LossRunSummaryResponse(
            assessment_id=assessment_id,
            total_claims=len(claims),
            open_claims=open_claims,
            closed_claims=closed_claims,
            years_of_history=years_of_history,
            total_paid=total_paid,
            total_reserved=total_reserved,
            total_incurred=total_paid + total_reserved,
            average_severity=(total_paid + total_reserved) / len(claims) if claims else None,
            claim_frequency=len(claims) / years_of_history if years_of_history else None,
            largest_claim_amount=float(largest.total_incurred) if largest else None,
            largest_claim_type=largest.claim_type if largest else None,
            files_uploaded=len(unique_files),
        )

    return LossRunSummaryResponse(
        assessment_id=assessment_id,
        total_claims=summary.total_claims,
        open_claims=summary.open_claims,
        closed_claims=summary.closed_claims,
        years_of_history=summary.years_of_history,
        total_paid=float(summary.total_paid or 0),
        total_reserved=float(summary.total_reserved or 0),
        total_incurred=float(summary.total_incurred or 0),
        average_severity=summary.average_severity,
        claim_frequency=summary.claim_frequency,
        largest_claim_amount=float(summary.largest_claim_amount) if summary.largest_claim_amount else None,
        largest_claim_type=summary.largest_claim_type,
        files_uploaded=0,  # Would need separate tracking
    )


@router.get("/{assessment_id}/raw")
async def get_raw_file_url(
    assessment_id: str,
    filename: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get presigned URL to download raw loss run file."""
    assessment = await get_assessment_or_404(assessment_id, db, current_user)

    # Find the S3 key for this filename
    result = await db.execute(
        select(InsuredLossRun.raw_file_path).where(
            InsuredLossRun.assessment_id == assessment_id,
            InsuredLossRun.raw_filename == filename,
        ).limit(1)
    )
    s3_key = result.scalar_one_or_none()

    if not s3_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    s3 = get_documents_client()
    url = s3.get_presigned_url(s3_key, expiration=3600)

    return {"url": url, "filename": filename, "expires_in": 3600}


@router.delete("/{assessment_id}/{claim_id}")
async def delete_claim(
    assessment_id: str,
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific claim from an assessment."""
    assessment = await get_assessment_or_404(assessment_id, db, current_user)

    try:
        claim_uuid = uuid.UUID(claim_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid claim ID format",
        )

    result = await db.execute(
        delete(InsuredLossRun).where(
            InsuredLossRun.id == claim_uuid,
            InsuredLossRun.assessment_id == assessment_id,
        )
    )

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )

    await db.commit()

    return {"success": True, "message": "Claim deleted"}


@router.post("/{assessment_id}/reparse")
async def reparse_loss_runs(
    assessment_id: str,
    filename: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-parse loss run file(s) for an assessment.

    If filename is provided, only that file is reparsed.
    Otherwise, all files are reparsed.
    """
    assessment = await get_assessment_or_404(assessment_id, db, current_user)

    # Get files to reparse
    query = select(InsuredLossRun.raw_file_path, InsuredLossRun.raw_filename).where(
        InsuredLossRun.assessment_id == assessment_id
    ).distinct()

    if filename:
        query = query.where(InsuredLossRun.raw_filename == filename)

    result = await db.execute(query)
    files = result.all()

    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No files found to reparse",
        )

    s3 = get_documents_client()
    parser = get_loss_run_parser()
    reparsed = []

    for s3_key, orig_filename in files:
        if not s3_key:
            continue

        # Delete existing claims for this file
        await db.execute(
            delete(InsuredLossRun).where(
                InsuredLossRun.assessment_id == assessment_id,
                InsuredLossRun.raw_file_path == s3_key,
            )
        )

        # Download and reparse
        try:
            content = s3.download_file(s3_key)
            file_obj = BytesIO(content)

            # Need to manually set the S3 key since file already exists
            parse_result = await parser.parse_file(
                file_obj=file_obj,
                filename=orig_filename,
                assessment_id=assessment_id,
            )

            # Store new claims
            for claim in parse_result.claims:
                db_claim = InsuredLossRun(
                    id=uuid.uuid4(),
                    assessment_id=assessment_id,
                    raw_file_path=s3_key,
                    raw_filename=orig_filename,
                    claim_number=claim.claim_number,
                    claim_date=claim.claim_date,
                    report_date=claim.report_date,
                    close_date=claim.close_date,
                    policy_year=claim.policy_year,
                    claim_type=claim.claim_type,
                    claim_description=claim.claim_description,
                    claimant_name=claim.claimant_name,
                    amount_paid=claim.amount_paid,
                    amount_reserved=claim.amount_reserved,
                    expense_paid=claim.expense_paid,
                    expense_reserved=claim.expense_reserved,
                    parsed_at=datetime.utcnow(),
                    parsing_confidence=claim.parsing_confidence,
                    row_number=claim.row_number,
                )
                db.add(db_claim)

            reparsed.append({
                "filename": orig_filename,
                "claims_parsed": len(parse_result.claims),
                "success": parse_result.success,
            })

        except Exception as e:
            logger.error(f"Reparse error for {orig_filename}: {e}")
            reparsed.append({
                "filename": orig_filename,
                "claims_parsed": 0,
                "success": False,
                "error": str(e),
            })

    await db.commit()

    return {
        "success": True,
        "files_reparsed": len(reparsed),
        "results": reparsed,
    }


# Background tasks
async def index_loss_run_for_rag(
    assessment_id: str,
    filename: str,
    claims: list,
):
    """Index loss run data in Qdrant for RAG search."""
    try:
        from app.services.rag_indexer import rag_indexer as indexer

        # Create a text representation of the loss run
        text_parts = [f"Loss Run Report: {filename}"]
        text_parts.append(f"Assessment: {assessment_id}")
        text_parts.append(f"Total Claims: {len(claims)}")

        for claim in claims[:50]:  # Limit to first 50 for indexing
            parts = []
            if claim.claim_number:
                parts.append(f"Claim #{claim.claim_number}")
            if claim.claim_date:
                parts.append(f"Date: {claim.claim_date}")
            if claim.claim_type:
                parts.append(f"Type: {claim.claim_type}")
            if claim.amount_paid:
                parts.append(f"Paid: ${claim.amount_paid:,.2f}")
            if claim.claim_description:
                parts.append(claim.claim_description[:200])
            text_parts.append(" | ".join(parts))

        full_text = "\n".join(text_parts)

        await indexer.index_document(
            doc_id=f"lossrun_{assessment_id}_{filename}",
            text=full_text,
            metadata={
                "type": "loss_run",
                "assessment_id": assessment_id,
                "filename": filename,
                "claim_count": len(claims),
            },
        )

        logger.info(f"Indexed loss run {filename} for RAG")

    except Exception as e:
        logger.error(f"Failed to index loss run for RAG: {e}")


async def update_loss_run_summary(assessment_id: str):
    """Update cached loss run summary for an assessment."""
    # This would need a database session from a new context
    # Implementation depends on how background tasks access DB
    logger.info(f"Would update loss run summary for {assessment_id}")
