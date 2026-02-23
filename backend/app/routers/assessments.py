"""
InstantRisk V2 - Assessments Router

This module provides endpoints for assessment CRUD operations
and AI-powered risk analysis.
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select, func, cast, Float
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, get_current_syndicate_user
from app.models.user import User
from app.models.assessment import (
    Assessment,
    AssessmentStatus,
    AssessmentDecision,
    RiskCategory,
)
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentUpdate,
    AssessmentResponse,
    AssessmentListResponse,
    AssessmentDecisionUpdate,
    AssessmentSummary,
)
from app.services.ai_service import AIService

router = APIRouter()


def generate_reference_number() -> str:
    """
    Generate a unique reference number for an assessment.

    Returns:
        str: Unique reference number in format IR-YYYYMMDD-XXXX.
    """
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique_part = uuid.uuid4().hex[:6].upper()
    return f"IR-{date_part}-{unique_part}"


async def run_ai_analysis(assessment_id: str, user_id: str = None):
    """
    Background task to run AI analysis on an assessment.
    Creates its own database session to avoid closed-session issues.
    """
    import logging

    logger = logging.getLogger("instantrisk.analysis")

    # Create a fresh database session for the background task
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Assessment).where(Assessment.id == assessment_id)
            )
            assessment = result.scalar_one_or_none()

            if not assessment:
                logger.error(f"Assessment {assessment_id} not found for analysis")
                return

            assessment.status = AssessmentStatus.IN_PROGRESS
            await db.commit()
            logger.info(f"Starting AI analysis for assessment {assessment_id}")

            # Run AI analysis (with user training doc context)
            ai_service = AIService()
            analysis_result = await ai_service.analyze_risk(
                assessment, user_id=str(user_id) if user_id else None
            )

            assessment.risk_score = analysis_result.get("risk_score")
            assessment.confidence_score = analysis_result.get("confidence_score")
            assessment.ai_analysis = analysis_result.get("analysis", {})
            assessment.ai_recommendations = analysis_result.get("recommendations", [])

            # Apply extracted fields from AI analysis (inception_date, expiry_date, etc.)
            extracted = analysis_result.get("extracted_fields", {}) or {}
            if extracted:
                from dateutil.parser import parse as parse_date

                # inception_date
                if not assessment.inception_date and extracted.get("inception_date"):
                    try:
                        assessment.inception_date = parse_date(
                            extracted["inception_date"]
                        )
                    except Exception:
                        pass

                # expiry_date
                if not assessment.expiry_date and extracted.get("expiry_date"):
                    try:
                        assessment.expiry_date = parse_date(extracted["expiry_date"])
                    except Exception:
                        pass

                # If we got inception but no expiry, default to inception + 1 year
                if assessment.inception_date and not assessment.expiry_date:
                    from datetime import timedelta

                    assessment.expiry_date = assessment.inception_date + timedelta(
                        days=365
                    )

                # broker_name
                if not assessment.broker_name and extracted.get("broker_name"):
                    assessment.broker_name = extracted["broker_name"]

                # insured_entity_name
                if not assessment.insured_entity_name and extracted.get(
                    "insured_entity_name"
                ):
                    assessment.insured_entity_name = extracted["insured_entity_name"]

                # territory
                if not assessment.territory and extracted.get("territory"):
                    assessment.territory = extracted["territory"]

            # Parse AI decision into assessment decision
            analysis = analysis_result.get("analysis", {})
            decision_str = (
                (
                    analysis_result.get("suggested_decision")
                    or analysis.get("decision")
                    or analysis_result.get("decision")
                    or ""
                )
                .lower()
                .strip()
            )

            risk_score = analysis_result.get("risk_score", 50)

            if decision_str:
                if "no" in decision_str and "go" in decision_str:
                    assessment.decision = AssessmentDecision.NO_GO
                elif (
                    "go" in decision_str
                    or "accept" in decision_str
                    or "approve" in decision_str
                ):
                    assessment.decision = AssessmentDecision.GO
                elif "decline" in decision_str or "reject" in decision_str:
                    assessment.decision = AssessmentDecision.NO_GO
                elif "refer" in decision_str:
                    assessment.decision = AssessmentDecision.REFER
                else:
                    if risk_score <= 50:
                        assessment.decision = AssessmentDecision.GO
                    elif risk_score <= 75:
                        assessment.decision = AssessmentDecision.REFER
                    else:
                        assessment.decision = AssessmentDecision.NO_GO
            else:
                if risk_score <= 50:
                    assessment.decision = AssessmentDecision.GO
                elif risk_score <= 75:
                    assessment.decision = AssessmentDecision.REFER
                else:
                    assessment.decision = AssessmentDecision.NO_GO

            assessment.status = AssessmentStatus.PENDING_REVIEW
            await db.commit()
            logger.info(
                f"AI analysis completed for {assessment_id}: score={assessment.risk_score}, decision={assessment.decision}"
            )

            # Auto-build entity graph via Companies House after analysis
            company_name = (
                assessment.insured_entity_name
                or assessment.insured_name
                or assessment.title
            )
            if company_name:
                try:
                    from app.services.entity_graph_service import build_entity_graph

                    graph = await build_entity_graph(company_name, depth=2)
                    if graph and graph.entities:
                        logger.info(
                            f"Entity graph built for '{company_name}': "
                            f"{len(graph.entities)} entities, {len(graph.relationships)} relationships"
                        )
                except Exception as eg_err:
                    logger.warning(
                        f"Entity graph build failed for '{company_name}': {eg_err}"
                    )

        except Exception as e:
            logger.error(f"AI analysis failed for {assessment_id}: {e}")
            try:
                assessment.status = AssessmentStatus.DRAFT
                assessment.ai_analysis = {"error": str(e)}
                await db.commit()
            except Exception:
                await db.rollback()


@router.post(
    "/", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED
)
async def create_assessment(
    assessment_data: AssessmentCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Assessment:
    """Create a new risk assessment."""
    try:
        reference_number = generate_reference_number()

        assessment = Assessment(
            reference_number=reference_number,
            title=assessment_data.title,
            description=assessment_data.description,
            risk_category=assessment_data.risk_category,
            created_by=current_user.id,
            syndicate_id=getattr(assessment_data, "syndicate_id", None),
            insured_name=getattr(assessment_data, "insured_name", None),
            insured_entity_name=getattr(assessment_data, "insured_entity_name", None),
            companies_house_number=getattr(
                assessment_data, "companies_house_number", None
            ),
            broker_reference=getattr(assessment_data, "broker_reference", None),
            broker_name=getattr(assessment_data, "broker_name", None),
            commission_rate=getattr(assessment_data, "commission_rate", None),
            premium=getattr(assessment_data, "premium", None),
            sum_insured=getattr(assessment_data, "sum_insured", None),
            deductible=getattr(assessment_data, "deductible", None),
            inception_date=getattr(assessment_data, "inception_date", None),
            expiry_date=getattr(assessment_data, "expiry_date", None)
            or (
                (
                    getattr(assessment_data, "inception_date", None)
                    or datetime.now(timezone.utc)
                )
                + timedelta(days=365)
            ),
            renewal_date=getattr(assessment_data, "renewal_date", None),
            territory=getattr(assessment_data, "territory", None),
            exposure_details=getattr(assessment_data, "exposure_details", None) or {},
            loss_run_reporting_rules=getattr(
                assessment_data, "loss_run_reporting_rules", None
            ),
            regulatory_framework=getattr(assessment_data, "regulatory_framework", None),
            status=AssessmentStatus.DRAFT,
            decision=AssessmentDecision.PENDING,
        )

        db.add(assessment)
        await db.commit()
        await db.refresh(assessment)

        return assessment
    except Exception as e:
        import traceback

        error_detail = traceback.format_exc()
        print(f"CREATE ASSESSMENT ERROR: {error_detail}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create assessment: {str(e)}"
        )


@router.get("/", response_model=AssessmentListResponse)
async def list_assessments(
    status: Optional[AssessmentStatus] = None,
    decision: Optional[AssessmentDecision] = None,
    risk_category: Optional[RiskCategory] = None,
    syndicate_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List assessments with optional filters and pagination.

    Args:
        status: Filter by assessment status.
        decision: Filter by decision type.
        risk_category: Filter by risk category.
        syndicate_id: Filter by syndicate ID.
        search: Search in title, insured name, or reference number.
        page: Page number (1-indexed).
        page_size: Number of items per page.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: Paginated list of assessments.
    """
    try:
        # Build query
        query = select(Assessment)
        count_query = select(func.count(Assessment.id))

        # Filter by user's role (case-insensitive comparison)
        user_role = current_user.role.lower() if current_user.role else ""
        if user_role == "broker":
            query = query.where(Assessment.created_by == current_user.id)
            count_query = count_query.where(Assessment.created_by == current_user.id)
        elif user_role == "syndicate" and current_user.syndicate_id:
            query = query.where(Assessment.syndicate_id == current_user.syndicate_id)
            count_query = count_query.where(
                Assessment.syndicate_id == current_user.syndicate_id
            )

        # Apply filters
        if status:
            query = query.where(Assessment.status == status)
            count_query = count_query.where(Assessment.status == status)
        if decision:
            query = query.where(Assessment.decision == decision)
            count_query = count_query.where(Assessment.decision == decision)
        if risk_category:
            query = query.where(Assessment.risk_category == risk_category)
            count_query = count_query.where(Assessment.risk_category == risk_category)
        if syndicate_id:
            query = query.where(Assessment.syndicate_id == syndicate_id)
            count_query = count_query.where(Assessment.syndicate_id == syndicate_id)
        if search:
            search_filter = (
                Assessment.title.ilike(f"%{search}%")
                | Assessment.insured_name.ilike(f"%{search}%")
                | Assessment.reference_number.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Get total count
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Order and paginate
        query = query.order_by(Assessment.created_at.desc())
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        assessments = result.scalars().all()

        # Calculate pagination
        pages = (total + page_size - 1) // page_size

        return {
            "items": assessments,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }
    except Exception as e:
        import traceback

        error_detail = traceback.format_exc()
        print(f"LIST ASSESSMENTS ERROR: {error_detail}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list assessments: {str(e)}"
        )


@router.get("/summary", response_model=AssessmentSummary)
async def get_assessment_summary(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get summary statistics for assessments.

    Args:
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: Assessment summary statistics.
    """
    # Base query filter by role
    base_filter = []
    if current_user.role == "broker":
        base_filter.append(Assessment.created_by == current_user.id)
    elif current_user.role == "syndicate" and current_user.syndicate_id:
        base_filter.append(Assessment.syndicate_id == current_user.syndicate_id)

    # Total count
    total_query = select(func.count(Assessment.id))
    if base_filter:
        total_query = total_query.where(*base_filter)
    total_result = await db.execute(total_query)
    total = total_result.scalar() or 0

    # Pending count
    pending_query = select(func.count(Assessment.id)).where(
        Assessment.status.in_(
            [
                AssessmentStatus.DRAFT,
                AssessmentStatus.PENDING_REVIEW,
                AssessmentStatus.IN_PROGRESS,
            ]
        )
    )
    if base_filter:
        pending_query = pending_query.where(*base_filter)
    pending_result = await db.execute(pending_query)
    pending = pending_result.scalar() or 0

    # Completed count
    completed_query = select(func.count(Assessment.id)).where(
        Assessment.status == AssessmentStatus.COMPLETED
    )
    if base_filter:
        completed_query = completed_query.where(*base_filter)
    completed_result = await db.execute(completed_query)
    completed = completed_result.scalar() or 0

    # Decision counts
    go_query = select(func.count(Assessment.id)).where(
        Assessment.decision == AssessmentDecision.GO
    )
    no_go_query = select(func.count(Assessment.id)).where(
        Assessment.decision == AssessmentDecision.NO_GO
    )

    if base_filter:
        go_query = go_query.where(*base_filter)
        no_go_query = no_go_query.where(*base_filter)

    go_result = await db.execute(go_query)
    no_go_result = await db.execute(no_go_query)

    # Average risk score
    avg_query = select(func.avg(cast(Assessment.risk_score, Float))).where(
        Assessment.risk_score.isnot(None)
    )
    if base_filter:
        avg_query = avg_query.where(*base_filter)
    avg_result = await db.execute(avg_query)
    avg_risk = avg_result.scalar()

    return {
        "total_assessments": total,
        "pending_count": pending,
        "completed_count": completed,
        "go_decisions": go_result.scalar() or 0,
        "no_go_decisions": no_go_result.scalar() or 0,
        "refer_decisions": 0,
        "average_risk_score": round(avg_risk, 2) if avg_risk else 0.0,
    }


@router.get("/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Assessment:
    """
    Get assessment details by ID.

    Args:
        assessment_id: The assessment ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        Assessment: The assessment object.

    Raises:
        HTTPException: If assessment not found or access denied.
    """
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    # Check access based on role
    if current_user.role == "broker" and assessment.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    elif (
        current_user.role == "syndicate"
        and assessment.syndicate_id != current_user.syndicate_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    return assessment


@router.get("/{assessment_id}/status")
async def get_assessment_status(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get assessment analysis status for polling fallback."""
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if assessment.status in (
        AssessmentStatus.COMPLETED,
        AssessmentStatus.PENDING_REVIEW,
    ):
        return {
            "status": "completed",
            "result": {
                "decision": assessment.decision.value
                if assessment.decision
                else "PENDING",
                "confidence": (assessment.confidence_score or 70) / 100,
                "risk_score": assessment.risk_score or 50,
                "processing_time": int(
                    (assessment.completed_at - assessment.created_at).total_seconds()
                )
                if assessment.completed_at
                else 0,
            },
        }
    elif assessment.status == AssessmentStatus.FAILED:
        return {"status": "failed", "error": "Analysis failed"}
    elif assessment.status == AssessmentStatus.DRAFT:
        # DRAFT after analysis means it errored but was caught
        has_analysis = bool(
            assessment.ai_analysis and not isinstance(assessment.ai_analysis, dict)
        )
        has_error = (
            isinstance(assessment.ai_analysis, dict)
            and "error" in assessment.ai_analysis
        )
        if has_error:
            return {
                "status": "failed",
                "error": assessment.ai_analysis.get("error", "Analysis failed"),
            }
        return {"status": "in_progress", "progress": 10}
    else:
        return {"status": "in_progress", "progress": 50}


@router.put("/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(
    assessment_id: str,
    assessment_data: AssessmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Assessment:
    """
    Update an existing assessment.

    Args:
        assessment_id: The assessment ID.
        assessment_data: Assessment update data.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        Assessment: The updated assessment object.

    Raises:
        HTTPException: If assessment not found or access denied.
    """
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    # Check access - only creator or admin can update
    if assessment.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    # Cannot update completed assessments
    if assessment.status == AssessmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a completed assessment",
        )

    # Update fields
    update_data = assessment_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(assessment, field, value)

    await db.commit()
    await db.refresh(assessment)

    return assessment


@router.post("/{assessment_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ai_analysis(
    assessment_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Trigger AI analysis for an assessment.

    Args:
        assessment_id: The assessment ID.
        background_tasks: FastAPI background tasks.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: Analysis trigger confirmation.

    Raises:
        HTTPException: If assessment not found or access denied.
    """
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    # Check access
    if assessment.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    # Queue AI analysis (creates its own DB session)
    background_tasks.add_task(run_ai_analysis, assessment.id, user_id=current_user.id)

    return {
        "message": "AI analysis queued",
        "assessment_id": assessment.id,
        "reference_number": assessment.reference_number,
    }


@router.post("/{assessment_id}/decision", response_model=AssessmentResponse)
async def set_assessment_decision(
    assessment_id: str,
    decision_data: AssessmentDecisionUpdate,
    current_user: User = Depends(get_current_syndicate_user),
    db: AsyncSession = Depends(get_db),
) -> Assessment:
    """
    Set the GO/NO-GO decision for an assessment.

    This endpoint is restricted to syndicate users and admins.

    Args:
        assessment_id: The assessment ID.
        decision_data: Decision update data.
        current_user: The authenticated syndicate user.
        db: Database session.

    Returns:
        Assessment: The updated assessment object.

    Raises:
        HTTPException: If assessment not found or access denied.
    """
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    # Check syndicate access
    if (
        current_user.role == "syndicate"
        and assessment.syndicate_id != current_user.syndicate_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Assessment not assigned to your syndicate",
        )

    # Set decision
    assessment.set_decision(decision_data.decision, decision_data.decision_rationale)

    await db.commit()
    await db.refresh(assessment)

    return assessment


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete an assessment.

    Args:
        assessment_id: The assessment ID to delete.
        current_user: The authenticated user.
        db: Database session.

    Raises:
        HTTPException: If assessment not found or access denied.
    """
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    # Only creator or admin can delete
    if assessment.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    # Cannot delete completed assessments
    if assessment.status == AssessmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a completed assessment",
        )

    await db.delete(assessment)
    await db.commit()


@router.get("/{assessment_id}/documents")
async def get_assessment_documents(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get uploaded documents for an assessment.

    Returns documents from the linked upload session.

    Args:
        assessment_id: The assessment ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: List of uploaded documents.
    """
    from app.models.upload_session import UploadSession
    import json

    # Get assessment to verify access
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    # Check access based on role
    if current_user.role == "broker" and assessment.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    elif (
        current_user.role == "syndicate"
        and assessment.syndicate_id != current_user.syndicate_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    # First, get documents from the documents table
    from app.models.document import Document

    doc_result = await db.execute(
        select(Document).where(Document.assessment_id == assessment_id)
    )
    db_documents = doc_result.scalars().all()

    documents = []
    for doc in db_documents:
        documents.append(
            {
                "id": doc.id,
                "name": doc.filename,
                "url": f"/api/v1/documents/{doc.id}/download",
                "file_path": doc.file_path,
                "mime_type": doc.mime_type,
                "file_size": doc.file_size,
                "document_type": doc.document_type.value
                if doc.document_type
                else "other",
                "uploaded_at": doc.created_at.isoformat() if doc.created_at else None,
                "processed_at": doc.processed_at.isoformat()
                if doc.processed_at
                else None,
                "type": "document",
                "status": doc.status.value if doc.status else "completed",
            }
        )

    # Also check upload session for any documents not in documents table
    session_result = await db.execute(
        select(UploadSession).where(UploadSession.assessment_id == assessment_id)
    )
    upload_session = session_result.scalar_one_or_none()

    if upload_session and upload_session.documents_json and not documents:
        try:
            docs = json.loads(upload_session.documents_json)
            for doc in docs:
                documents.append(
                    {
                        "id": doc.get("id"),
                        "name": doc.get("filename", doc.get("name", "Document")),
                        "url": doc.get("url"),
                        "uploaded_at": doc.get("uploaded_at"),
                        "type": "uploaded",
                        "status": "processed",
                    }
                )
        except json.JSONDecodeError:
            pass

    return {"items": documents, "total": len(documents), "assessment_id": assessment_id}


@router.get("/{assessment_id}/generated")
async def get_assessment_generated_documents(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get AI-generated documents for an assessment.

    Args:
        assessment_id: The assessment ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: List of generated documents.
    """
    from app.models.generated_document import GeneratedDocument

    # Get assessment to verify access
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    # Check access based on role
    if current_user.role == "broker" and assessment.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )
    elif (
        current_user.role == "syndicate"
        and assessment.syndicate_id != current_user.syndicate_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    # Get generated documents
    gen_result = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.assessment_id == assessment_id
        )
    )
    gen_documents = gen_result.scalars().all()

    items = []
    for doc in gen_documents:
        items.append(
            {
                "id": doc.id,
                "title": doc.title,
                "document_type": doc.document_type,
                "status": doc.status,
                "ai_confidence": doc.ai_confidence,
                "draft_content": doc.draft_content,
                "compliance_report": doc.compliance_report,
                "placeholders_remaining": doc.placeholders_remaining,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            }
        )

    return {"items": items, "total": len(items), "assessment_id": assessment_id}


@router.post("/{assessment_id}/upgrade-analysis")
async def upgrade_analysis(
    assessment_id: str,
    target_mode: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Upgrade an existing assessment to a deeper analysis mode.

    Allows users to upgrade from quick → go_no_go → deep for more detailed analysis.

    Args:
        assessment_id: The assessment ID to upgrade.
        target_mode: Target analysis mode (go_no_go or deep).
        background_tasks: FastAPI background tasks.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: Session info for WebSocket connection.
    """
    import asyncio
    import json
    from app.models.document import Document
    from app.models.upload_session import UploadSession

    # Validate target mode
    valid_modes = ["quick", "go_no_go", "deep"]
    if target_mode not in valid_modes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode. Must be one of: {', '.join(valid_modes)}",
        )

    # Get assessment
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    # Verify ownership
    if assessment.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    # Check upgrade is valid (can only go deeper, not shallower)
    mode_order = {"quick": 1, "go_no_go": 2, "deep": 3}
    current_mode = assessment.analysis_mode or "quick"

    if mode_order.get(target_mode, 0) <= mode_order.get(current_mode, 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot downgrade or repeat analysis. Current mode: {current_mode}, requested: {target_mode}",
        )

    # Get documents for this assessment
    doc_result = await db.execute(
        select(Document).where(Document.assessment_id == assessment_id)
    )
    documents = doc_result.scalars().all()

    # If no documents in documents table, check upload session
    file_paths = []
    if documents:
        file_paths = [d.file_path for d in documents if d.file_path]

    # If no documents found, check upload session
    if not file_paths:
        session_result = await db.execute(
            select(UploadSession).where(UploadSession.assessment_id == assessment_id)
        )
        upload_session = session_result.scalar_one_or_none()
        if upload_session and upload_session.documents_json:
            try:
                docs = json.loads(upload_session.documents_json)
                for doc in docs:
                    # Try to get path directly
                    if doc.get("path"):
                        file_paths.append(doc["path"])
                    # Or convert URL to file path
                    elif doc.get("url"):
                        url = doc["url"]
                        # Extract path from URL: https://host/uploads/token/file.pdf -> /var/www/instantrisk-v2/uploads/token/file.pdf
                        if "/uploads/" in url:
                            relative_path = url.split("/uploads/", 1)[1]
                            file_path = (
                                f"/var/www/instantrisk-v2/uploads/{relative_path}"
                            )
                            if os.path.exists(file_path):
                                file_paths.append(file_path)
            except json.JSONDecodeError:
                pass

    if not file_paths:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No documents found for re-analysis",
        )

    # Store previous analysis
    assessment.previous_analysis_json = assessment.ai_analysis
    assessment.status = AssessmentStatus.IN_PROGRESS
    await db.commit()

    # Generate session ID for WebSocket
    ws_session_id = f"upgrade-{assessment_id}-{target_mode}-{uuid.uuid4().hex[:8]}"

    # Start background re-analysis
    async def run_upgrade_analysis():
        from app.core.database import AsyncSessionLocal
        from app.routers.analysis import send_progress_update

        async with AsyncSessionLocal() as db_session:
            try:
                # Get fresh assessment reference
                result = await db_session.execute(
                    select(Assessment).where(Assessment.id == assessment_id)
                )
                assessment_ref = result.scalar_one_or_none()
                if not assessment_ref:
                    return

                # Initialize processor - use the existing document_processor which handles PDF/OCR
                from app.services.document_processor import document_processor

                # Send start message
                await send_progress_update(
                    ws_session_id,
                    {
                        "type": "start",
                        "mode": target_mode,
                        "message": f"Upgrading to {target_mode} analysis...",
                    },
                )

                # Run analysis using document_processor which handles PDF extraction
                if len(file_paths) == 1:
                    analysis = await document_processor.analyze_document(
                        file_paths[0], mode=target_mode
                    )
                else:
                    analysis = await document_processor.analyze_multiple_documents(
                        file_paths, mode=target_mode
                    )

                # Add analysis mode to results
                analysis["analysis_mode"] = target_mode

                # Update assessment
                decision_str = analysis.get("decision", "refer").lower()
                if "go" in decision_str and "no" not in decision_str:
                    decision = AssessmentDecision.GO
                elif "no" in decision_str or "decline" in decision_str:
                    decision = AssessmentDecision.NO_GO
                else:
                    decision = AssessmentDecision.NO_GO

                risk_score = analysis.get("risk_score", 50)
                confidence = analysis.get("confidence", 0.5)
                if isinstance(confidence, (int, float)):
                    confidence = float(confidence)
                    if confidence > 1:
                        confidence = confidence / 100

                assessment_ref.status = AssessmentStatus.COMPLETED
                assessment_ref.decision = decision
                assessment_ref.risk_score = risk_score
                assessment_ref.confidence_score = int(confidence * 100)
                assessment_ref.ai_analysis = analysis
                assessment_ref.analysis_mode = target_mode
                assessment_ref.completed_at = datetime.now(timezone.utc)
                # Store RapidRate pricing results if available
                agent_results = analysis.get("agent_results", {})
                if agent_results.get("rapidrate_pricing"):
                    assessment_ref.rapidrate_results = agent_results[
                        "rapidrate_pricing"
                    ]
                await db_session.commit()

                # Send completion message
                await send_progress_update(
                    ws_session_id,
                    {
                        "type": "complete",
                        "decision": decision.value,
                        "confidence": confidence,
                        "risk_score": risk_score,
                        "assessment_id": assessment_id,
                    },
                )

            except Exception as e:
                import traceback

                traceback.print_exc()
                await send_progress_update(
                    ws_session_id, {"type": "error", "message": str(e)}
                )

    # Start background task
    asyncio.create_task(run_upgrade_analysis())

    return {
        "success": True,
        "session_id": ws_session_id,
        "message": f"Upgrading to {target_mode} analysis",
        "websocket_url": f"/api/v1/analysis/ws/{ws_session_id}",
        "assessment_id": assessment_id,
    }


@router.get("/{assessment_id}/analysis-history")
async def get_analysis_history(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get analysis history including any upgrades.

    Args:
        assessment_id: The assessment ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        dict: Analysis history with current and previous analyses.
    """
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    # Verify access
    if assessment.created_by != current_user.id and current_user.role != "admin":
        if (
            current_user.role == "syndicate"
            and assessment.syndicate_id != current_user.syndicate_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

    history = []

    # Add previous analysis if exists
    if assessment.previous_analysis_json:
        prev_mode = assessment.previous_analysis_json.get("analysis_mode", "quick")
        history.append(
            {
                "mode": prev_mode,
                "analysis": assessment.previous_analysis_json,
                "is_current": False,
            }
        )

    # Add current analysis
    current_mode = assessment.analysis_mode or assessment.ai_analysis.get(
        "analysis_mode", "unknown"
    )
    history.append(
        {
            "mode": current_mode,
            "analysis": assessment.ai_analysis,
            "is_current": True,
            "decision": assessment.decision.value if assessment.decision else None,
            "risk_score": assessment.risk_score,
            "confidence_score": assessment.confidence_score,
        }
    )

    return {
        "assessment_id": assessment_id,
        "current_mode": current_mode,
        "can_upgrade": current_mode != "deep",
        "next_mode": "go_no_go"
        if current_mode == "quick"
        else ("deep" if current_mode == "go_no_go" else None),
        "history": history,
    }


@router.post("/{assessment_id}/ml-analyze")
async def ml_analyze_assessment(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Run InstantRisk Engine ML analysis on an assessment.

    Uses the fine-tuned multi-task model to produce:
    - Clause category recommendations (134 categories, multi-label)
    - Risk appetite assessment (accept / refer / decline)
    - Pricing band classification (low / medium / high)
    - Insurance intent classification (39 intent types)

    If the user has a trained personal adapter, predictions are personalized
    to their portfolio history.

    Returns structured predictions alongside model availability status.
    Falls back gracefully when the model is not loaded.
    """
    from app.services.insurance_model_service import insurance_model_service

    # Fetch assessment
    result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment not found: {assessment_id}",
        )

    # Access control
    if assessment.created_by != current_user.id and current_user.role not in (
        "admin",
        "syndicate",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    user_id = str(current_user.id)

    # Build risk text from assessment fields
    assessment_dict = {
        "risk_category": assessment.risk_category.value
        if assessment.risk_category
        else "",
        "territory": assessment.territory or "",
        "summary": assessment.description or "",
        "insured_entity_name": assessment.insured_entity_name or "",
        "insured_name": getattr(assessment, "insured_name", "") or "",
        "extracted_data": assessment.ai_analysis or {},
    }

    if not insurance_model_service.is_available:
        # Model not loaded — return fallback with explanation
        return {
            "assessment_id": assessment_id,
            "model_available": False,
            "model_name": "InstantRisk Engine v1",
            "message": "ML model not loaded — running in fallback mode. "
            "Ensure model files exist in app/data/models/instantrisk-engine-v1-final/",
            "predictions": {
                "clauses": [],
                "appetite": {
                    "decision": "refer",
                    "confidence": 0.0,
                    "scores": {"accept": 0.33, "refer": 0.34, "decline": 0.33},
                },
                "pricing": {
                    "band": "medium",
                    "confidence": 0.0,
                    "scores": {"low": 0.33, "medium": 0.34, "high": 0.33},
                },
                "intent": {"intent": "unknown", "confidence": 0.0, "top_intents": []},
                "personalized": False,
            },
            "risk_text_used": "",
        }

    try:
        risk_text = insurance_model_service.build_risk_description(assessment_dict)
        predictions = insurance_model_service.predict_all(risk_text, user_id=user_id)

        return {
            "assessment_id": assessment_id,
            "model_available": True,
            "model_name": "InstantRisk Engine v1",
            "base_model": insurance_model_service._config.get("base_model", ""),
            "personalized": predictions.get("personalized", False),
            "predictions": predictions,
            "risk_text_used": risk_text,
            "label_counts": {
                "clause_labels": insurance_model_service._config.get(
                    "num_clause_labels", 0
                ),
                "intent_labels": insurance_model_service._config.get(
                    "num_intent_labels", 0
                ),
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ML analysis failed: {str(e)}",
        )


@router.get("/{assessment_id}/precedents", summary="Find similar precedent assessments")
async def get_assessment_precedents(
    assessment_id: str,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Proxy to precedent search for this assessment."""
    from app.services.precedent_search import precedent_search_service

    try:
        aid = uuid.UUID(assessment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid assessment ID")

    assessment = await db.get(Assessment, aid)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    try:
        similar = await precedent_search_service.find_similar(
            db=db, assessment_id=aid, top_k=limit, min_similarity=0.5, filters={}
        )
        return {
            "query_assessment_id": assessment_id,
            "similar_assessments": similar,
            "count": len(similar),
        }
    except Exception:
        return {
            "query_assessment_id": assessment_id,
            "similar_assessments": [],
            "count": 0,
        }


@router.get(
    "/{assessment_id}/breach-alerts", summary="Get breach alerts for assessment"
)
async def get_assessment_breach_alerts(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get data breach alerts for the assessment's insured entity."""
    from app.models.risk_alert import RiskMonitoringAlert

    try:
        aid = uuid.UUID(assessment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid assessment ID")

    assessment = await db.get(Assessment, aid)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    result = await db.execute(
        select(RiskMonitoringAlert)
        .where(RiskMonitoringAlert.assessment_id == aid)
        .order_by(RiskMonitoringAlert.detected_at.desc())
        .limit(20)
    )
    alerts = result.scalars().all()

    return {
        "assessment_id": assessment_id,
        "alerts": [
            {
                "id": a.id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "message": a.message,
                "source": a.source,
                "detected_at": a.detected_at.isoformat() if a.detected_at else None,
                "acknowledged": a.acknowledged,
            }
            for a in alerts
        ],
        "count": len(alerts),
    }


@router.get(
    "/{assessment_id}/entities", summary="Get entity relationships for assessment"
)
async def get_assessment_entities(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get entity graph data for this assessment."""
    try:
        aid = uuid.UUID(assessment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid assessment ID")

    assessment = await db.get(Assessment, aid)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    company_name = (
        assessment.insured_entity_name
        or getattr(assessment, "insured_name", None)
        or ""
    )

    if not company_name:
        return {
            "assessment_id": assessment_id,
            "company_name": "",
            "entities": [],
            "relationships": [],
            "fraud_signals": [],
        }

    try:
        from app.services.entity_graph_service import (
            get_entity_graph,
            entity_graph_to_dict,
        )

        graph_data = await get_entity_graph(company_name)
        if graph_data:
            nodes, edges = graph_data
            return {
                "assessment_id": assessment_id,
                "company_name": company_name,
                "entities": nodes,
                "relationships": edges,
                "fraud_signals": [],
            }
    except Exception:
        pass

    return {
        "assessment_id": assessment_id,
        "company_name": company_name,
        "entities": [],
        "relationships": [],
        "fraud_signals": [],
    }
