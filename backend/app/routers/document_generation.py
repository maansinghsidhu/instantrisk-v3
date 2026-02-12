"""
Document Generation Router - AI-Powered Insurance Document Generation

Endpoints for generating insurance documents from assessments
using the 5-agent AutoGen pipeline.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db, AsyncSessionLocal
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.models.template import Template
from app.models.generated_document import GeneratedDocument, DocumentGenerationJob
from app.schemas.generated_document import (
    DocumentSuggestion,
    DocumentSuggestionResponse,
    LMAClauseSuggestion,
    GenerationJobCreate,
    GenerationJobProgress,
    GenerationStepProgress,
    GenerationJobResponse,
    GeneratedDocumentResponse,
    GeneratedDocumentListResponse,
    GeneratedDocumentUpdate,
    PrefillRequest,
    PrefillResponse,
    FinalizeRequest,
    FinalizeResponse
)
from app.services.document_generator import document_generator
from app.services.reference_document_service import reference_document_service
from app.services.insurance_templates import get_all_templates, get_template
from app.services.lma_clauses_service import LMAClausesService
from app.services.translation_service import translation_service
from app.data.clause_service import get_clause_service
from app.services.qdrant_service import qdrant_service
from app.models.user import SupportedLanguage
from app.config import settings

# Initialize clause services
lma_clauses_service = LMAClausesService()
clause_service = get_clause_service()  # Full 33k+ clause library

router = APIRouter()


def _parse_doc_id(doc_id: str) -> int | None:
    """Parse a document ID from the frontend.

    The frontend may send string IDs like "gen_1770850906225" or plain
    integer strings like "42".  This helper strips the "gen_" prefix
    (if present) and converts the remainder to an integer suitable for
    the DB lookup.  Returns None when the value cannot be parsed.
    """
    if doc_id is None:
        return None
    raw = doc_id
    # Strip known string prefixes produced by the frontend
    for prefix in ("gen_", "doc_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


@router.post("/assessments/{assessment_id}/suggest-documents", response_model=DocumentSuggestionResponse)
async def suggest_documents(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get AI-suggested documents for an assessment.

    Analyzes the assessment and recommends which documents
    should be generated based on risk category and decision.
    Uses the comprehensive clause library with proper recommendations.
    """
    # Get assessment
    query = select(Assessment).where(
        Assessment.id == assessment_id,
        Assessment.created_by == current_user.id
    )
    result = await db.execute(query)
    assessment = result.scalars().first()

    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Build assessment dict
    risk_category = assessment.risk_category.value if assessment.risk_category else "general"
    territory = assessment.territory or ""
    sum_insured = float(assessment.sum_insured) if assessment.sum_insured else None

    # Extract perils and special features from AI analysis
    perils = []
    special_features = []
    ai_analysis = assessment.ai_analysis or {}

    # Extract risk factors from AI analysis
    if isinstance(ai_analysis, dict):
        # Get perils from risk_factors or identified_risks
        risk_factors = ai_analysis.get("risk_factors", [])
        if isinstance(risk_factors, list):
            for factor in risk_factors:
                if isinstance(factor, str):
                    perils.append(factor)
                elif isinstance(factor, dict):
                    perils.append(factor.get("name", factor.get("factor", "")))

        identified_risks = ai_analysis.get("identified_risks", [])
        if isinstance(identified_risks, list):
            for risk in identified_risks:
                if isinstance(risk, str):
                    perils.append(risk)
                elif isinstance(risk, dict):
                    perils.append(risk.get("name", risk.get("risk", "")))

        # Get special features
        features = ai_analysis.get("special_features", ai_analysis.get("notable_features", []))
        if isinstance(features, list):
            special_features.extend(features)

        # Check for specific keywords in analysis
        summary = ai_analysis.get("summary", "") or ""
        if "cyber" in summary.lower():
            special_features.append("cyber")
        if "climate" in summary.lower() or "environmental" in summary.lower():
            special_features.append("climate")
        if "cryptocurrency" in summary.lower() or "crypto" in summary.lower():
            special_features.append("cryptocurrency")
        if "ai" in summary.lower() or "artificial intelligence" in summary.lower():
            special_features.append("ai")

    assessment_data = {
        "id": assessment.id,
        "reference_number": assessment.reference_number,
        "title": assessment.title,
        "risk_category": risk_category,
        "decision": assessment.decision.value if assessment.decision else None,
        "insured_name": assessment.insured_name,
        "broker_reference": assessment.broker_reference,
        "premium": assessment.premium,
        "sum_insured": assessment.sum_insured,
        "deductible": assessment.deductible,
        "territory": territory,
        "inception_date": str(assessment.inception_date) if assessment.inception_date else None,
        "expiry_date": str(assessment.expiry_date) if assessment.expiry_date else None,
        "risk_score": assessment.risk_score,
        "ai_analysis": ai_analysis,
        "perils": perils,
        "special_features": special_features,
    }

    # Get suggestions from AI for documents
    suggestions = await document_generator.suggest_documents(assessment_data)

    # Get COMPREHENSIVE clause recommendations from clause service
    # This returns ALL relevant clauses from the bank, categorized properly
    clause_recommendations = lma_clauses_service.recommend_clauses(
        risk_category=risk_category,
        territory=territory,
        perils=perils if perils else None,
        sum_insured=sum_insured,
        special_features=special_features if special_features else None
    )

    # Build comprehensive LMA clauses list with proper categorization
    lma_clauses = []

    # Add mandatory clauses (always selected)
    for clause in clause_recommendations.get("mandatory", []):
        lma_clauses.append(LMAClauseSuggestion(
            id=clause.get("id", ""),
            name=clause.get("name", ""),
            mandatory=True,
            category=clause.get("category", "general"),
            selected=True,  # Pre-selected
            reason=f"Required for {risk_category} policies"
        ))

    # Add recommended clauses (pre-selected)
    for clause in clause_recommendations.get("recommended", []):
        lma_clauses.append(LMAClauseSuggestion(
            id=clause.get("id", ""),
            name=clause.get("name", ""),
            mandatory=False,
            category=clause.get("category", "general"),
            selected=True,  # Pre-selected as recommended
            reason=f"Recommended for {risk_category} in {territory or 'worldwide'}"
        ))

    # Add optional clauses (not pre-selected, available for user to add)
    for clause in clause_recommendations.get("optional", []):
        lma_clauses.append(LMAClauseSuggestion(
            id=clause.get("id", ""),
            name=clause.get("name", ""),
            mandatory=False,
            category=clause.get("category", "general"),
            selected=False,  # Available but not pre-selected
            reason="Available for inclusion if needed"
        ))

    # Also add ALL other clauses from the library for search/browse
    all_clauses = lma_clauses_service.get_all_clauses()
    existing_ids = {c.id for c in lma_clauses}

    for clause in all_clauses:
        if clause.get("id") not in existing_ids:
            lma_clauses.append(LMAClauseSuggestion(
                id=clause.get("id", ""),
                name=clause.get("name", ""),
                mandatory=False,
                category=clause.get("category", "general"),
                selected=False,
                reason="Available in clause library"
            ))

    # Map to response schema
    return DocumentSuggestionResponse(
        assessment_id=assessment_id,
        risk_category=risk_category,
        decision=assessment_data.get("decision", ""),
        suggested_documents=[
            DocumentSuggestion(
                document_type=doc.get("document_type", ""),
                template_id=doc.get("template_id"),
                template_key=doc.get("template_key", ""),
                template_name=doc.get("template_key", "").replace("_", " ").title(),
                priority=doc.get("priority", 1),
                mandatory=doc.get("mandatory", False),
                confidence=doc.get("confidence", 0.0),
                reason=doc.get("reason", "")
            )
            for doc in suggestions.get("suggested_documents", [])
        ],
        bundle_name=suggestions.get("bundle_name", "Document Bundle"),
        total_estimated_time_seconds=suggestions.get("total_estimated_time_seconds", 60),
        lma_clauses=lma_clauses
    )


@router.post("/assessments/{assessment_id}/generate-documents", response_model=GenerationJobResponse)
async def generate_documents(
    assessment_id: str,
    request: GenerationJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start document generation for an assessment.

    Creates a generation job that runs the 5-agent pipeline
    to generate the requested documents.

    Training documents are optional but improve AI output quality.
    A warning is returned if no training documents exist.
    """
    # Check if user has training documents (informational, not blocking)
    training_count = await qdrant_service.count_training_docs(str(current_user.id))
    training_warnings = []
    if training_count == 0:
        training_warnings.append(
            "No training documents found. Uploading sample policies, endorsements, "
            "and other documents on the Training page will improve AI document quality. "
            "Generation will proceed using built-in templates and clause libraries."
        )

    # Get assessment with eager-loaded documents to avoid lazy loading issues
    query = select(Assessment).options(
        selectinload(Assessment.documents)
    ).where(
        Assessment.id == assessment_id,
        Assessment.created_by == current_user.id
    )
    result = await db.execute(query)
    assessment = result.scalars().first()

    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Get templates (static + database)
    templates = get_all_templates()

    # Also get database templates
    db_templates_query = select(Template).where(Template.is_active == True)
    db_result = await db.execute(db_templates_query)
    db_templates = db_result.scalars().all()

    # Merge templates
    all_templates = templates + [
        {
            "id": t.id,
            "template_key": t.template_key,
            "name": t.name,
            "category": t.category,
            "document_type": t.document_type,
            "fields": t.fields,
            "sections": t.sections
        }
        for t in db_templates
    ]

    # Create job record
    job_id = str(uuid.uuid4())[:8]
    job = DocumentGenerationJob(
        id=job_id,
        assessment_id=assessment_id,
        status="pending",
        total_documents=len(request.document_types),
        document_suggestions=[{"document_type": dt, "status": "pending"} for dt in request.document_types]
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Build assessment dict
    assessment_data = {
        "id": assessment.id,
        "reference_number": assessment.reference_number,
        "title": assessment.title,
        "risk_category": assessment.risk_category.value if assessment.risk_category else None,
        "decision": assessment.decision.value if assessment.decision else None,
        "insured_name": assessment.insured_name,
        "broker_reference": assessment.broker_reference,
        "premium": assessment.premium,
        "sum_insured": assessment.sum_insured,
        "deductible": assessment.deductible,
        "territory": assessment.territory,
        "inception_date": str(assessment.inception_date) if assessment.inception_date else None,
        "expiry_date": str(assessment.expiry_date) if assessment.expiry_date else None,
        "risk_score": assessment.risk_score,
        "ai_analysis": assessment.ai_analysis
    }

    # Get extracted data from linked documents
    extracted_data = {}
    for doc in assessment.documents:
        if doc.extracted_data:
            extracted_data.update(doc.extracted_data)

    # Run generation in background (don't pass db session - create new one in task)
    background_tasks.add_task(
        _run_generation_job,
        job_id,
        assessment_data,
        all_templates,
        request.document_types,
        extracted_data,
        request.clause_ids,  # Pass selected clause IDs
        request.language     # Pass target language
    )

    return GenerationJobResponse(
        id=job.id,
        assessment_id=str(job.assessment_id),
        status=job.status,
        total_documents=job.total_documents,
        completed_documents=0,
        progress_percentage=0,
        warnings=training_warnings if training_warnings else None,
        created_at=job.created_at
    )


async def _update_job_progress(job_id: str, agent: str, description: str, percentage: int):
    """Helper to update job progress in database."""
    async with AsyncSessionLocal() as db:
        try:
            job_query = select(DocumentGenerationJob).where(DocumentGenerationJob.id == job_id)
            result = await db.execute(job_query)
            job = result.scalars().first()
            if job:
                job.current_agent = agent
                job.current_agent_description = description
                job.progress_percentage = percentage
                await db.commit()
        except Exception:
            pass  # Don't fail on progress update errors


async def _run_generation_job(
    job_id: str,
    assessment_data: dict,
    templates: list,
    document_types: list,
    extracted_data: dict,
    clause_ids: list = None,
    language: str = None
):
    """Background task to run document generation.

    Creates its own database session to avoid issues with closed sessions.
    Updates progress in real-time during the generation pipeline.

    Args:
        clause_ids: Optional list of LMA clause IDs to include in documents
        language: Optional target language code for document generation
    """
    import logging
    logging.info(f"Starting document generation job {job_id} for assessment {assessment_data.get('id')}")

    # Real-time progress callback
    async def progress_callback(progress_data: dict):
        """Update job progress in real-time during document generation."""
        try:
            agent = progress_data.get("current_agent", "Processing")
            description = progress_data.get("current_description", "Processing documents...")

            # Use the progress_percentage calculated by the generator directly
            # The generator tracks precise progress: 5%, 15%, then per-document steps
            percentage = progress_data.get("progress_percentage", 20)

            # Ensure we stay within bounds (5% start, 95% max before completion)
            percentage = max(5, min(percentage, 95))

            await _update_job_progress(job_id, agent, description, percentage)
        except Exception as e:
            logging.warning(f"Progress update failed: {e}")

    async with AsyncSessionLocal() as db:
        try:
            # Update job status - Starting
            job_query = select(DocumentGenerationJob).where(DocumentGenerationJob.id == job_id)
            result = await db.execute(job_query)
            job = result.scalars().first()

            if job:
                job.start_processing()
                job.current_agent = "Initializing"
                job.current_agent_description = "Starting document generation pipeline..."
                job.progress_percentage = 5
                await db.commit()

            # Step 1: Document Requirement Analyzer (10%)
            await _update_job_progress(
                job_id,
                "DocumentRequirementAnalyzer",
                "Analyzing assessment data and identifying document requirements...",
                10
            )

            # Step 2: Template Selector (15%)
            await _update_job_progress(
                job_id,
                "TemplateSelector",
                "Selecting optimal templates for requested documents...",
                15
            )

            # Step 3-5: Run actual generation pipeline with real-time progress
            # Progress will update from 20% to 95% during this phase
            await _update_job_progress(
                job_id,
                "DocumentGenerator",
                f"Generating {len(document_types)} documents...",
                20
            )

            results = await document_generator.generate_documents(
                assessment=assessment_data,
                templates=templates,
                document_types=document_types,
                extracted_data=extracted_data,
                progress_callback=progress_callback,
                clause_ids=clause_ids,
                language=language
            )

            # Final compliance check (95%)
            await _update_job_progress(
                job_id,
                "ComplianceChecker",
                "Final compliance verification...",
                95
            )

            # Store generated documents
            for gen_doc in results.get("generated_documents", []):
                # Handle template_id - static templates have string IDs, DB expects Integer or None
                raw_template_id = gen_doc.get("template_id")
                template_id = None
                if raw_template_id is not None:
                    try:
                        template_id = int(raw_template_id)
                    except (ValueError, TypeError):
                        # Static template with string ID - store as None (use template_key in draft_content)
                        template_id = None

                doc = GeneratedDocument(
                    assessment_id=assessment_data["id"],
                    generation_job_id=job_id,
                    template_id=template_id,
                    document_type=gen_doc.get("document_type"),
                    title=gen_doc.get("title"),
                    status=gen_doc.get("status", "draft"),
                    draft_content=gen_doc.get("draft_content", {}),
                    data_mappings=gen_doc.get("data_mappings", {}),
                    compliance_report=gen_doc.get("compliance_report", {}),
                    placeholders_remaining=gen_doc.get("placeholders_remaining", 0),
                    ai_confidence=gen_doc.get("ai_confidence")
                )
                db.add(doc)

            # Update job to completed (100%)
            job_query = select(DocumentGenerationJob).where(DocumentGenerationJob.id == job_id)
            result = await db.execute(job_query)
            job = result.scalars().first()
            if job:
                job.agent_outputs = results.get("agent_outputs", {})
                job.current_agent = "Complete"
                job.current_agent_description = "Document generation completed successfully"
                job.progress_percentage = 100
                job.complete()
                job.completed_documents = len(results.get("generated_documents", []))
                await db.commit()

        except Exception as e:
            # Log the error
            import logging
            logging.error(f"Document generation job {job_id} failed: {str(e)}", exc_info=True)
            # Mark job as failed with new session to ensure it commits
            async with AsyncSessionLocal() as error_db:
                job_query = select(DocumentGenerationJob).where(DocumentGenerationJob.id == job_id)
                result = await error_db.execute(job_query)
                job = result.scalars().first()
                if job:
                    job.fail(str(e))
                    await error_db.commit()


@router.get("/generation-jobs/")
async def list_generation_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all generation jobs for the current user."""
    assessment_query = select(Assessment.id).where(Assessment.created_by == current_user.id)
    assessment_result = await db.execute(assessment_query)
    assessment_ids = [a[0] for a in assessment_result.fetchall()]
    if not assessment_ids:
        return []
    query = select(DocumentGenerationJob).where(
        DocumentGenerationJob.assessment_id.in_(assessment_ids)
    ).order_by(DocumentGenerationJob.created_at.desc())
    result = await db.execute(query)
    jobs = result.scalars().all()
    return [GenerationJobResponse.model_validate(job) for job in jobs]


@router.get("/generation-jobs/{job_id}/status", response_model=GenerationJobProgress)
async def get_generation_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the status of a document generation job with detailed step progress."""
    query = select(DocumentGenerationJob).where(DocumentGenerationJob.id == job_id)
    result = await db.execute(query)
    job = result.scalars().first()

    if not job:
        raise HTTPException(404, "Job not found")

    # Build steps array showing exact pipeline progress
    progress = job.progress_percentage or 0
    pipeline_steps = [
        ("Initializing", "Starting document generation pipeline...", 5),
        ("DocumentRequirementAnalyzer", "Analyzing assessment data and identifying document requirements...", 10),
        ("TemplateSelector", "Selecting optimal templates for requested documents...", 30),
        ("DataMapper", "Mapping assessment data to template fields...", 50),
        ("DocumentDrafter", "Drafting document content with AI assistance...", 70),
        ("ComplianceChecker", "Verifying compliance and validating document content...", 90),
        ("Complete", "Document generation completed successfully", 100),
    ]

    steps = []
    for agent, description, threshold in pipeline_steps:
        if progress >= threshold:
            status = "completed"
        elif job.current_agent == agent:
            status = "running"
        else:
            status = "pending"
        steps.append(GenerationStepProgress(
            agent=agent,
            description=description,
            percentage=threshold,
            status=status
        ))

    return GenerationJobProgress(
        job_id=job.id,
        status=job.status,
        current_agent=job.current_agent,
        current_agent_description=job.current_agent_description,
        progress_percentage=job.progress_percentage or 0,
        completed_documents=job.completed_documents or 0,
        total_documents=job.total_documents or 0,
        steps=steps,
        error_message=job.error_message if hasattr(job, 'error_message') else None
    )


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobResponse)
async def get_generation_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get full details of a generation job."""
    query = select(DocumentGenerationJob).where(DocumentGenerationJob.id == job_id)
    result = await db.execute(query)
    job = result.scalars().first()

    if not job:
        raise HTTPException(404, "Job not found")

    return GenerationJobResponse(
        id=job.id,
        assessment_id=str(job.assessment_id),
        status=job.status,
        total_documents=job.total_documents,
        completed_documents=job.completed_documents,
        progress_percentage=job.progress_percentage,
        current_agent=job.current_agent,
        current_agent_description=job.current_agent_description,
        created_at=job.created_at,
        completed_at=job.completed_at
    )


@router.get("/assessments/{assessment_id}/generated", response_model=GeneratedDocumentListResponse)
async def list_generated_documents(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all generated documents for an assessment."""
    # Verify assessment ownership
    assessment_result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.created_by == current_user.id
        )
    )
    if not assessment_result.scalar_one_or_none():
        raise HTTPException(404, "Assessment not found or access denied")

    query = select(GeneratedDocument).where(
        GeneratedDocument.assessment_id == assessment_id
    ).order_by(GeneratedDocument.created_at.desc())

    result = await db.execute(query)
    documents = result.scalars().all()

    return GeneratedDocumentListResponse(
        items=[GeneratedDocumentResponse.model_validate(doc) for doc in documents],
        total=len(documents)
    )


@router.get("/generated-documents/", response_model=GeneratedDocumentListResponse)
async def list_all_generated_documents(
    page: int = 1,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all generated documents for the current user across all assessments."""
    # Get assessments owned by user
    assessment_query = select(Assessment.id).where(Assessment.created_by == current_user.id)
    assessment_result = await db.execute(assessment_query)
    assessment_ids = [a[0] for a in assessment_result.fetchall()]

    if not assessment_ids:
        return GeneratedDocumentListResponse(items=[], total=0)

    # Get generated documents for those assessments
    query = select(GeneratedDocument).where(
        GeneratedDocument.assessment_id.in_(assessment_ids)
    ).order_by(GeneratedDocument.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    documents = result.scalars().all()

    # Get total count
    count_query = select(GeneratedDocument).where(
        GeneratedDocument.assessment_id.in_(assessment_ids)
    )
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    return GeneratedDocumentListResponse(
        items=[GeneratedDocumentResponse.model_validate(doc) for doc in documents],
        total=total
    )


@router.get("/generated-documents/{doc_id}", response_model=GeneratedDocumentResponse)
async def get_generated_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single generated document."""
    # Parse doc_id: frontend may send string IDs like "gen_1770850906225" or plain integers
    parsed_id = _parse_doc_id(doc_id)
    if parsed_id is None:
        raise HTTPException(400, f"Invalid document ID format: {doc_id}")

    # Join with Assessment to verify ownership
    query = (
        select(GeneratedDocument)
        .join(Assessment, GeneratedDocument.assessment_id == Assessment.id)
        .where(
            GeneratedDocument.id == parsed_id,
            Assessment.created_by == current_user.id
        )
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(404, "Document not found or access denied")

    return GeneratedDocumentResponse.model_validate(doc)


@router.put("/generated-documents/{doc_id}", response_model=GeneratedDocumentResponse)
async def update_generated_document(
    doc_id: str,
    update_data: GeneratedDocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a generated document (e.g., edit content)."""
    # Parse doc_id: frontend may send string IDs like "gen_1770850906225" or plain integers
    parsed_id = _parse_doc_id(doc_id)
    if parsed_id is None:
        raise HTTPException(400, f"Invalid document ID format: {doc_id}")

    # Join with Assessment to verify ownership
    query = (
        select(GeneratedDocument)
        .join(Assessment, GeneratedDocument.assessment_id == Assessment.id)
        .where(
            GeneratedDocument.id == parsed_id,
            Assessment.created_by == current_user.id
        )
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(404, "Document not found or access denied")

    if update_data.title:
        doc.title = update_data.title
    if update_data.final_content:
        doc.final_content = update_data.final_content
        doc.status = "approved"

    await db.commit()
    await db.refresh(doc)

    return GeneratedDocumentResponse.model_validate(doc)


@router.post("/assessments/{assessment_id}/prefill/{template_id}", response_model=PrefillResponse)
async def prefill_template(
    assessment_id: str,
    template_id: str,
    request: PrefillRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get AI-prefilled data for a template based on assessment.

    Optionally uses RAG from reference documents for enhancement.
    """
    # Get assessment with eager-loaded documents
    query = select(Assessment).options(
        selectinload(Assessment.documents)
    ).where(
        Assessment.id == assessment_id,
        Assessment.created_by == current_user.id
    )
    result = await db.execute(query)
    assessment = result.scalars().first()

    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Get template (try static first, then database)
    template = get_template(template_id)
    if not template:
        # Try database
        try:
            tid = int(template_id)
            t_query = select(Template).where(Template.id == tid)
            t_result = await db.execute(t_query)
            t = t_result.scalars().first()
            if t:
                template = {
                    "id": t.id,
                    "name": t.name,
                    "fields": t.fields,
                    "sections": t.sections
                }
        except (ValueError, TypeError):
            pass

    if not template:
        raise HTTPException(404, "Template not found")

    # Build assessment dict
    assessment_data = {
        "id": assessment.id,
        "reference_number": assessment.reference_number,
        "title": assessment.title,
        "risk_category": assessment.risk_category.value if assessment.risk_category else None,
        "decision": assessment.decision.value if assessment.decision else None,
        "insured_name": assessment.insured_name,
        "broker_reference": assessment.broker_reference,
        "premium": assessment.premium,
        "sum_insured": assessment.sum_insured,
        "deductible": assessment.deductible,
        "territory": assessment.territory,
        "inception_date": str(assessment.inception_date) if assessment.inception_date else None,
        "expiry_date": str(assessment.expiry_date) if assessment.expiry_date else None,
    }

    # Get extracted data from documents
    extracted_data = {}
    for doc in assessment.documents:
        if doc.extracted_data:
            extracted_data.update(doc.extracted_data)

    # Get RAG context if requested
    rag_context = None
    if request and request.include_rag:
        rag_context = await reference_document_service.get_rag_context(
            query=f"{assessment.title} {assessment.risk_category.value if assessment.risk_category else ''} policy wording",
            risk_category=assessment.risk_category.value if assessment.risk_category else None,
            limit=3
        )

    # Get prefill data
    prefill = await document_generator.prefill_template(
        assessment=assessment_data,
        template=template,
        extracted_data=extracted_data,
        rag_context=rag_context
    )

    return PrefillResponse(
        template_id=template.get("id"),
        template_name=template.get("name"),
        field_mappings=prefill.get("field_mappings", {}),
        unmapped_fields=prefill.get("unmapped_fields", []),
        data_conflicts=prefill.get("data_conflicts", []),
        completion_percentage=prefill.get("completion_percentage", 0),
        rag_context_used=rag_context is not None,
        rag_sources=[]
    )


@router.post("/generated-documents/{doc_id}/finalize", response_model=FinalizeResponse)
async def finalize_document(
    doc_id: str,
    request: FinalizeRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Finalize a document and generate PDF.
    """
    # Parse doc_id: frontend may send string IDs like "gen_1770850906225" or plain integers
    parsed_id = _parse_doc_id(doc_id)
    if parsed_id is None:
        raise HTTPException(400, f"Invalid document ID format: {doc_id}")

    # Join with Assessment to verify ownership
    query = (
        select(GeneratedDocument)
        .join(Assessment, GeneratedDocument.assessment_id == Assessment.id)
        .where(
            GeneratedDocument.id == parsed_id,
            Assessment.created_by == current_user.id
        )
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(404, "Document not found or access denied")

    # Update content if provided
    if request and request.final_content:
        doc.final_content = request.final_content

    # Generate PDF using WeasyPrint
    pdf_filename = f"{doc.document_type}_{doc.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_dir = os.path.join(settings.upload_dir, "generated")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    # Get document content and parse sections
    raw_content = doc.final_content or doc.draft_content or {}

    # Build HTML sections from structured content
    def _build_sections_html(content_data):
        """Convert structured JSON sections into formatted HTML."""
        import html as html_mod

        if isinstance(content_data, str):
            # Plain text fallback
            return f'<div class="section"><p>{html_mod.escape(content_data)}</p></div>'

        if not isinstance(content_data, dict):
            return '<div class="section"><p>No content available.</p></div>'

        sections = content_data.get("sections", [])
        doc_title = content_data.get("document_title", "")
        parts = []

        if doc_title:
            parts.append(f'<h1 class="doc-title">{html_mod.escape(doc_title)}</h1>')

        for section in sections:
            title = section.get("section_title", "") or section.get("heading", "")
            body = section.get("content", "")

            parts.append('<div class="section">')
            if title:
                parts.append(f'<h2 class="section-title">{html_mod.escape(title)}</h2>')

            if body:
                # Convert line breaks to paragraphs and handle bullet points
                paragraphs = body.split("\n\n")
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    lines = para.split("\n")
                    # Check if this looks like a list
                    is_list = all(
                        line.strip().startswith(("-", "•", "*", "–"))
                        or not line.strip()
                        for line in lines if line.strip()
                    )
                    if is_list:
                        parts.append("<ul>")
                        for line in lines:
                            line = line.strip().lstrip("-•*– ").strip()
                            if line:
                                parts.append(f"<li>{html_mod.escape(line)}</li>")
                        parts.append("</ul>")
                    else:
                        parts.append(f"<p>{html_mod.escape(para)}</p>")

            parts.append("</div>")

        return "\n".join(parts)

    sections_html = _build_sections_html(raw_content)

    # Get document title from content or fallback
    doc_title = ""
    if isinstance(raw_content, dict):
        doc_title = raw_content.get("document_title", "")
    if not doc_title:
        doc_title = doc.document_type.upper().replace('_', ' ')

    # Create HTML template for PDF
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: 'Times New Roman', Times, serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #333;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                border-bottom: 2px solid #1a365d;
                padding-bottom: 20px;
            }}
            .header h1 {{
                color: #1a365d;
                font-size: 20pt;
                margin: 0;
                letter-spacing: 1px;
            }}
            .header p {{
                color: #666;
                font-size: 10pt;
                margin: 5px 0 0 0;
            }}
            .meta {{
                background: #f7fafc;
                padding: 15px;
                margin-bottom: 25px;
                border-radius: 5px;
                border-left: 4px solid #1a365d;
            }}
            .meta-item {{
                display: inline-block;
                margin-right: 30px;
            }}
            .meta-label {{
                font-weight: bold;
                color: #1a365d;
            }}
            .doc-title {{
                text-align: center;
                color: #1a365d;
                font-size: 16pt;
                margin: 20px 0;
            }}
            .section {{
                margin-bottom: 20px;
                page-break-inside: avoid;
            }}
            .section-title {{
                color: #1a365d;
                font-size: 13pt;
                font-weight: bold;
                margin-top: 20px;
                margin-bottom: 10px;
                padding-bottom: 5px;
                border-bottom: 1px solid #e2e8f0;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .section p {{
                margin: 8px 0;
                text-align: justify;
            }}
            .section ul {{
                margin: 8px 0;
                padding-left: 25px;
            }}
            .section li {{
                margin-bottom: 4px;
            }}
            .footer {{
                position: fixed;
                bottom: 1cm;
                left: 2cm;
                right: 2cm;
                text-align: center;
                font-size: 9pt;
                color: #666;
                border-top: 1px solid #ddd;
                padding-top: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{doc_title}</h1>
            <p>Document ID: {doc.id} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        <div class="meta">
            <div class="meta-item">
                <span class="meta-label">Document Type:</span> {doc.document_type.replace('_', ' ').title()}
            </div>
            <div class="meta-item">
                <span class="meta-label">Status:</span> Finalized
            </div>
        </div>
        {sections_html}
        <div class="footer">
            InstantRisk - AI-Powered Underwriting Platform | Confidential
        </div>
    </body>
    </html>
    """

    # Generate PDF with WeasyPrint
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_template).write_pdf()

        with open(pdf_path, 'wb') as f:
            f.write(pdf_bytes)

        pdf_size = len(pdf_bytes)
    except Exception as e:
        # Fallback: create a simple text-based PDF if WeasyPrint fails
        import logging
        logging.error(f"WeasyPrint PDF generation failed: {e}")
        # Create empty placeholder file
        pdf_size = 0
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')  # Minimal PDF header

    doc.mark_finalized(pdf_path, pdf_filename, pdf_size)
    await db.commit()
    await db.refresh(doc)

    return FinalizeResponse(
        document_id=doc.id,
        status="finalized",
        pdf_url=f"/api/v1/generated-documents/{doc.id}/download",
        pdf_file_name=pdf_filename,
        pdf_file_size=0,
        finalized_at=doc.finalized_at
    )


@router.get("/generated-documents/{doc_id}/download")
async def download_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Download a finalized document PDF."""
    # Parse doc_id: frontend may send string IDs like "gen_1770850906225" or plain integers
    parsed_id = _parse_doc_id(doc_id)
    if parsed_id is None:
        raise HTTPException(400, f"Invalid document ID format: {doc_id}")

    # Join with Assessment to verify ownership
    query = (
        select(GeneratedDocument)
        .join(Assessment, GeneratedDocument.assessment_id == Assessment.id)
        .where(
            GeneratedDocument.id == parsed_id,
            Assessment.created_by == current_user.id
        )
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(404, "Document not found or access denied")

    if not doc.pdf_path:
        raise HTTPException(400, "Document has not been finalized")

    # Return file (placeholder)
    from fastapi.responses import FileResponse

    if os.path.exists(doc.pdf_path):
        return FileResponse(
            doc.pdf_path,
            media_type="application/pdf",
            filename=doc.pdf_file_name
        )
    else:
        raise HTTPException(404, "PDF file not found")


# =============================================================================
# V3 DOCUMENT GENERATION ENDPOINTS
# =============================================================================

import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Any

# Template paths
TEMPLATES_BASE_PATH = Path("/app/data/templates")
POLICIES_PATH = TEMPLATES_BASE_PATH / "policies"
CLAUSES_PATH = TEMPLATES_BASE_PATH / "clauses"


class GenerateDocumentV3Request(BaseModel):
    """Request for V3 document generation."""
    document_type: str = Field(..., description="Type of document to generate (policy, endorsement, certificate)")
    line_of_business: str = Field(..., description="Line of business (cyber, property, marine, etc.)")
    template_id: Optional[str] = Field(None, description="Specific template ID to use")
    selected_clauses: List[str] = Field(default_factory=list, description="List of clause IDs to include")
    variables: dict = Field(default_factory=dict, description="Variables to populate in the document")
    include_standard_clauses: bool = Field(True, description="Include standard mandatory clauses")
    language: Optional[str] = Field(None, description="Target language code (en, de, fr, es, it, pt, nl, ar, zh, ja). Uses user's preferred language if not specified.")


class GeneratedDocumentV3Response(BaseModel):
    """Response for V3 document generation."""
    document_id: str
    document_type: str
    line_of_business: str
    title: str
    template_used: Optional[str] = None
    sections: List[dict]
    clauses_included: List[dict]
    variables_applied: dict
    warnings: List[str] = []
    generated_at: datetime
    language: str = "en"


class ClauseSuggestion(BaseModel):
    """Suggested clause for a document."""
    clause_id: str
    clause_name: str
    clause_type: str
    is_mandatory: bool
    is_recommended: bool
    reason: str
    line_of_business: str


class SuggestClausesResponse(BaseModel):
    """Response for clause suggestions."""
    line_of_business: str
    document_type: str
    mandatory_clauses: List[ClauseSuggestion]
    recommended_clauses: List[ClauseSuggestion]
    optional_clauses: List[ClauseSuggestion]
    total_suggested: int


def _load_json_file(path: Path) -> Optional[dict]:
    """Load and parse a JSON file."""
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return None


def _load_policies_for_line(line: str) -> List[dict]:
    """Load all policy templates for a specific line of business."""
    policies = []
    line_path = POLICIES_PATH / line

    if line_path.exists() and line_path.is_dir():
        for json_file in line_path.glob("*.json"):
            policy = _load_json_file(json_file)
            if policy:
                policies.append(policy)

    return policies


def _load_all_clause_types() -> List[dict]:
    """Load all clause type files."""
    clause_types = []
    by_type_path = CLAUSES_PATH / "by_type"

    if by_type_path.exists():
        for json_file in by_type_path.glob("*.json"):
            clause_data = _load_json_file(json_file)
            if clause_data:
                clause_types.append(clause_data)

    return clause_types


def _get_clause_by_id(clause_id: str) -> Optional[dict]:
    """Get a specific clause by ID from the full 33k+ clause library."""
    # First try the comprehensive clause service (33k+ clauses)
    clause = clause_service.get_clause_by_id(clause_id)
    if clause:
        return clause

    # Fall back to V3 template files
    clause_types = _load_all_clause_types()
    for clause_type_data in clause_types:
        for c in clause_type_data.get("clauses", []):
            if c.get("id") == clause_id:
                return {
                    **c,
                    "clause_type": clause_type_data.get("type", "")
                }

    return None


def _get_mandatory_clauses(line_of_business: str, document_type: str) -> List[dict]:
    """Get mandatory clauses for a line of business and document type."""
    mandatory = []

    # Define mandatory clauses by line and document type
    mandatory_map = {
        "general": ["cond_001", "cond_008", "cond_010", "excl_001", "excl_002"],
        "cyber": ["excl_015", "cond_001", "cond_004"],
        "marine": ["cond_002", "cond_003", "cond_007", "excl_013"],
        "aviation": ["cond_006", "excl_014"],
        "property": ["excl_003", "excl_008", "cond_009"],
        "casualty": ["excl_006", "excl_007", "excl_012"],
        "professional_lines": ["excl_005", "excl_010", "excl_011"]
    }

    # Get line-specific mandatory clauses
    line_key = line_of_business.lower().replace(" ", "_")
    mandatory_ids = mandatory_map.get(line_key, []) + mandatory_map.get("general", [])
    mandatory_ids = list(set(mandatory_ids))  # Remove duplicates

    for clause_id in mandatory_ids:
        clause = _get_clause_by_id(clause_id)
        if clause:
            mandatory.append(clause)

    return mandatory


def _get_recommended_clauses(line_of_business: str, document_type: str) -> List[dict]:
    """Get recommended clauses for a line of business and document type."""
    recommended = []

    # Define recommended clauses by line
    recommended_map = {
        "cyber": ["lim_001", "lim_002", "ind_001", "def_001"],
        "marine": ["sub_001", "lim_003", "war_001"],
        "aviation": ["lim_004", "cond_011"],
        "property": ["cond_005", "cond_012", "lim_005"],
        "casualty": ["cond_004", "cond_013", "def_002"]
    }

    line_key = line_of_business.lower().replace(" ", "_")
    recommended_ids = recommended_map.get(line_key, [])

    for clause_id in recommended_ids:
        clause = _get_clause_by_id(clause_id)
        if clause:
            recommended.append(clause)

    return recommended


def _substitute_variables(text: str, variables: dict) -> str:
    """Substitute variables in text using {{variable}} syntax."""
    result = text
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value))
    return result


@router.post("/documents/generate-v3", response_model=GeneratedDocumentV3Response)
async def generate_document_v3(
    request: GenerateDocumentV3Request,
    current_user: User = Depends(get_current_user)
):
    """
    Generate a document using V3 template system with multi-language support.

    Uses templates from /backend/data/templates/ and allows selection
    of specific clauses to include in the generated document.
    Documents are automatically translated to the user's preferred language.

    Args:
        request: GenerateDocumentV3Request with generation parameters

    Returns:
        GeneratedDocumentV3Response with the generated document.
    """
    warnings = []

    # Determine target language
    target_language = None
    if request.language:
        try:
            target_language = SupportedLanguage(request.language)
        except ValueError:
            warnings.append(f"Invalid language code: {request.language}. Using English.")
            target_language = SupportedLanguage.ENGLISH
    elif current_user.preferred_language:
        target_language = current_user.preferred_language
    else:
        target_language = SupportedLanguage.ENGLISH

    # Normalize line of business
    line_lower = request.line_of_business.lower().replace(" ", "_")

    # Find template to use
    template_used = None
    sections = []

    if request.template_id:
        # Load specific template
        policies = _load_policies_for_line(line_lower)
        for policy in policies:
            if policy.get("id") == request.template_id:
                template_used = policy
                break

        if not template_used:
            # Try all lines
            for line_dir in POLICIES_PATH.iterdir():
                if line_dir.is_dir():
                    for policy in _load_policies_for_line(line_dir.name):
                        if policy.get("id") == request.template_id:
                            template_used = policy
                            break
                if template_used:
                    break

    if not template_used:
        # Find first matching template for line
        policies = _load_policies_for_line(line_lower)
        if policies:
            template_used = policies[0]
            warnings.append(f"No specific template requested. Using default: {template_used.get('name')}")
        else:
            warnings.append(f"No templates found for line: {line_lower}. Using generic structure.")

    # Build sections from template
    if template_used:
        for section in template_used.get("sections", []):
            section_content = section.get("content", "")
            # Substitute variables
            section_content = _substitute_variables(section_content, request.variables)

            sections.append({
                "name": section.get("name", ""),
                "content": section_content,
                "order": len(sections) + 1
            })

    # Add selected clauses
    clauses_included = []

    # Include mandatory clauses if requested
    if request.include_standard_clauses:
        mandatory = _get_mandatory_clauses(line_lower, request.document_type)
        for clause in mandatory:
            clause_text = _substitute_variables(clause.get("text", ""), request.variables)
            clauses_included.append({
                "id": clause.get("id", ""),
                "name": clause.get("name", ""),
                "text": clause_text,
                "type": clause.get("clause_type", ""),
                "is_mandatory": True
            })

    # Include explicitly selected clauses
    for clause_id in request.selected_clauses:
        # Skip if already included as mandatory
        if any(c.get("id") == clause_id for c in clauses_included):
            continue

        clause = _get_clause_by_id(clause_id)
        if clause:
            clause_text = _substitute_variables(clause.get("text", ""), request.variables)
            clauses_included.append({
                "id": clause.get("id", ""),
                "name": clause.get("name", ""),
                "text": clause_text,
                "type": clause.get("clause_type", ""),
                "is_mandatory": False
            })
        else:
            warnings.append(f"Clause not found: {clause_id}")

    # Generate document ID
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"

    # Determine title
    title = f"{request.document_type.title()} - {request.line_of_business.title()}"
    if request.variables.get("insured_name"):
        title = f"{title} - {request.variables.get('insured_name')}"

    # Translate content if not English
    if target_language and target_language != SupportedLanguage.ENGLISH:
        # Translate title
        title = await translation_service.translate_text(
            title,
            target_language,
            context="insurance document title"
        )

        # Translate sections
        translated_sections = []
        for section in sections:
            translated_section = section.copy()
            if section.get("name"):
                translated_section["name"] = await translation_service.translate_text(
                    section["name"],
                    target_language,
                    context="insurance document section header"
                )
            if section.get("content"):
                translated_section["content"] = await translation_service.translate_text(
                    section["content"],
                    target_language,
                    context="insurance document"
                )
            translated_section["original_language"] = "en"
            translated_section["translated_to"] = target_language.value
            translated_sections.append(translated_section)
        sections = translated_sections

        # Translate clauses
        translated_clauses = []
        for clause in clauses_included:
            translated_clause = await translation_service.translate_clause(
                clause,
                target_language
            )
            translated_clauses.append(translated_clause)
        clauses_included = translated_clauses

        warnings.append(f"Document translated to {target_language.value}")

    return GeneratedDocumentV3Response(
        document_id=doc_id,
        document_type=request.document_type,
        line_of_business=request.line_of_business,
        title=title,
        template_used=template_used.get("id") if template_used else None,
        sections=sections,
        clauses_included=clauses_included,
        variables_applied=request.variables,
        warnings=warnings,
        generated_at=datetime.now(timezone.utc),
        language=target_language.value if target_language else "en"
    )


@router.get("/clauses/suggest", response_model=SuggestClausesResponse)
async def suggest_clauses(
    line_of_business: str,
    document_type: str = "policy",
    current_user: User = Depends(get_current_user)
):
    """
    Get pre-selected clause suggestions for a line of business and document type.

    Analyzes the line of business and document type to recommend
    mandatory, recommended, and optional clauses.

    Args:
        line_of_business: Insurance line (cyber, property, marine, etc.)
        document_type: Type of document (policy, endorsement, certificate)

    Returns:
        SuggestClausesResponse with categorized clause suggestions.
    """
    line_lower = line_of_business.lower().replace(" ", "_")

    # Get mandatory clauses
    mandatory_clauses = _get_mandatory_clauses(line_lower, document_type)
    mandatory_suggestions = [
        ClauseSuggestion(
            clause_id=c.get("id", ""),
            clause_name=c.get("name", ""),
            clause_type=c.get("clause_type", ""),
            is_mandatory=True,
            is_recommended=True,
            reason=f"Required for {line_of_business} {document_type}",
            line_of_business=c.get("line_of_business", "general")
        )
        for c in mandatory_clauses
    ]

    # Get recommended clauses
    recommended_clauses = _get_recommended_clauses(line_lower, document_type)
    recommended_suggestions = [
        ClauseSuggestion(
            clause_id=c.get("id", ""),
            clause_name=c.get("name", ""),
            clause_type=c.get("clause_type", ""),
            is_mandatory=False,
            is_recommended=True,
            reason=f"Commonly included in {line_of_business} policies",
            line_of_business=c.get("line_of_business", "general")
        )
        for c in recommended_clauses
    ]

    # Get optional clauses from full 33k+ clause library
    optional_suggestions = []

    already_suggested = set(
        [c.clause_id for c in mandatory_suggestions] +
        [c.clause_id for c in recommended_suggestions]
    )

    # Use the comprehensive clause service (33k+ clauses)
    all_clauses = clause_service.get_all_clauses()

    # Also get clauses by category for the specific line
    line_clauses = clause_service.get_clauses_by_category(line_lower)

    # Combine and dedupe
    clause_map = {c.get("id"): c for c in all_clauses}
    for c in line_clauses:
        clause_map[c.get("id")] = c

    for clause_id, clause in clause_map.items():
        # Skip if already suggested
        if clause_id in already_suggested:
            continue

        clause_category = clause.get("category", "general")

        # Include if matches line or is a core/general clause
        if clause_category == line_lower or clause_category in ["core", "general", "claims", "sanctions"]:
            optional_suggestions.append(
                ClauseSuggestion(
                    clause_id=clause_id,
                    clause_name=clause.get("name", "")[:100],
                    clause_type=clause_category,
                    is_mandatory=False,
                    is_recommended=False,
                    reason=f"Available from {clause.get('source', 'clause library')}",
                    line_of_business=clause_category
                )
            )

        # Limit to prevent overwhelming response
        if len(optional_suggestions) >= 500:
            break

    total = len(mandatory_suggestions) + len(recommended_suggestions) + len(optional_suggestions)
    total_available = len(clause_service.get_all_clauses())

    return SuggestClausesResponse(
        line_of_business=line_of_business,
        document_type=document_type,
        mandatory_clauses=mandatory_suggestions,
        recommended_clauses=recommended_suggestions,
        optional_clauses=optional_suggestions,
        total_suggested=total
        # Note: total_available is {total_available} clauses in full library
    )


# =============================================================================
# AI-Driven Document Generation (OpenDraft Pipeline)
# =============================================================================

@router.post("/ai-recommend")
async def ai_recommend_documents(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI-driven document recommendation.
    Analyzes assessment and tells the user exactly what documents they need and why.
    Replaces the old hardcoded DOCUMENT_REQUIREMENTS mapping.
    """
    assessment_id = request.get("assessment_id")
    user_request = request.get("user_request")

    if not assessment_id:
        raise HTTPException(400, "assessment_id is required")

    # Load assessment
    query = select(Assessment).where(
        Assessment.id == assessment_id,
        Assessment.created_by == current_user.id
    )
    result = await db.execute(query)
    assessment = result.scalars().first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Try OpenDraft AI analysis
    try:
        from app.services.opendraft_generator import opendraft_generator
        assessment_data = {
            "id": assessment.id,
            "reference_number": assessment.reference_number,
            "title": assessment.title,
            "risk_category": assessment.risk_category.value if assessment.risk_category else "general",
            "decision": assessment.decision.value if assessment.decision else None,
            "insured_name": assessment.insured_name,
            "territory": assessment.territory or "",
            "premium": assessment.premium,
            "sum_insured": assessment.sum_insured,
            "ai_analysis": assessment.ai_analysis or {},
            "rapidrate_results": assessment.rapidrate_results or {},
        }

        if user_request:
            assessment_data["user_request"] = user_request

        recommendations = await opendraft_generator.analyze_assessment(
            assessment_data, str(current_user.id)
        )
        return {"recommended_documents": recommendations}
    except Exception as e:
        logger.error(f"AI document recommendation failed: {e}", exc_info=True)
        risk_category = assessment.risk_category.value if assessment.risk_category else "general"
        fallback = _get_fallback_recommendations(risk_category)
        return {"recommended_documents": fallback, "is_fallback": True}


@router.post("/ai-clauses")
async def ai_clause_search(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI-driven clause search with source attribution.
    Searches user's uploaded docs first, then ACORD, then AI generation.
    """
    assessment_id = request.get("assessment_id")
    document_types = request.get("document_types", [])

    if not assessment_id:
        raise HTTPException(400, "assessment_id is required")

    try:
        from app.services.opendraft_generator import opendraft_generator
        clauses = await opendraft_generator.search_clauses(
            document_types, str(current_user.id)
        )
        return {"clauses_by_document": clauses}
    except Exception as e:
        logger.error(f"AI clause search failed: {e}", exc_info=True)
        # Rich fallback with document-type-appropriate clauses
        clauses_by_doc = {}
        for doc_type in document_types:
            base_clauses = [
                {"clause_id": "preamble", "name": "Preamble & Recitals", "source": "template", "content_preview": "Standard opening recitals and parties identification...", "is_mandatory": True},
                {"clause_id": "insuring_agreement", "name": "Insuring Agreement", "source": "template", "content_preview": "The Insurer agrees to indemnify the Insured against...", "is_mandatory": True},
                {"clause_id": "exclusions", "name": "General Exclusions", "source": "template", "content_preview": "War, nuclear, sanctions and other standard exclusions...", "is_mandatory": True},
                {"clause_id": "conditions", "name": "General Conditions", "source": "template", "content_preview": "Duty of utmost good faith, claims notification, premium payment...", "is_mandatory": True},
                {"clause_id": "claims", "name": "Claims Procedure", "source": "template", "content_preview": "Claims notification requirements and procedure...", "is_mandatory": True},
                {"clause_id": "cancellation", "name": "Cancellation & Termination", "source": "template", "content_preview": "Cancellation rights, notice periods, return premium...", "is_mandatory": True},
                {"clause_id": "law_jurisdiction", "name": "Law & Jurisdiction", "source": "template", "content_preview": "English law and exclusive jurisdiction of English courts...", "is_mandatory": True},
            ]
            if doc_type in ("policy_wording", "endorsement"):
                base_clauses.extend([
                    {"clause_id": "definitions", "name": "Definitions", "source": "template", "content_preview": "Key terms and definitions used throughout this policy...", "is_mandatory": True},
                    {"clause_id": "premium", "name": "Premium & Payment", "source": "template", "content_preview": "Premium amount, payment schedule, and terms...", "is_mandatory": False},
                    {"clause_id": "subrogation", "name": "Subrogation", "source": "template", "content_preview": "Subrogation rights following claim settlement...", "is_mandatory": False},
                    {"clause_id": "lma5021", "name": "Several Liability Notice (LMA5021)", "source": "template", "content_preview": "Lloyd's several liability clause per LMA5021...", "is_mandatory": True},
                    {"clause_id": "sanctions", "name": "Sanctions Limitation (LMA5173)", "source": "template", "content_preview": "Sanctions compliance and limitation clause...", "is_mandatory": True},
                ])
            clauses_by_doc[doc_type] = base_clauses
        return {"clauses_by_document": clauses_by_doc, "is_fallback": True}


@router.post("/generate")
async def generate_documents_opendraft(
    request: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate documents using OpenDraft 7-agent pipeline.
    """
    assessment_id = request.get("assessment_id")
    documents = request.get("documents", [])
    clauses = request.get("clauses")

    if not assessment_id:
        raise HTTPException(400, "assessment_id is required")

    # Load assessment
    query = select(Assessment).where(
        Assessment.id == assessment_id,
        Assessment.created_by == current_user.id
    )
    result = await db.execute(query)
    assessment = result.scalars().first()
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    try:
        from app.services.opendraft_generator import opendraft_generator
        assessment_data = {
            "id": assessment.id,
            "reference_number": assessment.reference_number,
            "title": assessment.title,
            "risk_category": assessment.risk_category.value if assessment.risk_category else "general",
            "insured_name": assessment.insured_name,
            "territory": assessment.territory or "",
            "premium": assessment.premium,
            "sum_insured": assessment.sum_insured,
            "ai_analysis": assessment.ai_analysis or {},
            "rapidrate_results": assessment.rapidrate_results or {},
        }

        result = await opendraft_generator.generate(
            assessment_data=assessment_data,
            user_id=str(current_user.id),
            doc_types=documents,
        )

        return result
    except Exception as e:
        logger.error(f"Document generation failed: {e}", exc_info=True)
        return {
            "is_fallback": True,
            "error": str(e),
            "documents": [
                {
                    "id": f"gen_{assessment_id}_{doc_type}",
                    "name": doc_type.replace("_", " ").title(),
                    "type": doc_type,
                    "status": "draft",
                    "sections": 10,
                }
                for doc_type in documents
            ],
            "source_counts": {
                "user_uploaded": 0,
                "acord": 3,
                "ai_generated": len(documents) * 5,
            },
        }


def _get_fallback_recommendations(risk_category: str) -> list:
    """Basic document recommendations when AI is unavailable."""
    base = [
        {
            "type": "mrc_slip",
            "name": "MRC Slip",
            "reason": "Standard placement document for Lloyd's market submissions",
            "priority": "mandatory",
            "estimated_sections": 12,
        },
        {
            "type": "policy_wording",
            "name": "Policy Wording",
            "reason": "Full policy with terms, conditions, and coverage details",
            "priority": "mandatory",
            "estimated_sections": 18,
        },
        {
            "type": "endorsement_schedule",
            "name": "Endorsement Schedule",
            "reason": "List of endorsements and amendments to standard terms",
            "priority": "recommended",
            "estimated_sections": 8,
        },
    ]

    if risk_category in ("marine", "cargo", "hull"):
        base.append({
            "type": "war_risks_endorsement",
            "name": "War Risks Endorsement",
            "reason": "Marine risks typically require separate war risks coverage",
            "priority": "recommended",
            "estimated_sections": 4,
        })
    elif risk_category in ("property", "fire"):
        base.append({
            "type": "nat_cat_endorsement",
            "name": "Natural Catastrophe Endorsement",
            "reason": "Property risks need natural catastrophe sub-limits",
            "priority": "recommended",
            "estimated_sections": 5,
        })

    base.append({
        "type": "pricing_summary",
        "name": "Pricing Summary",
        "reason": "Technical pricing breakdown with rate derivation",
        "priority": "optional",
        "estimated_sections": 6,
    })

    return base
