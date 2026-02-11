"""
InstantRisk V3 - Document Extraction API Router

Provides endpoints for:
- Intelligent document extraction
- Document type detection
- Extraction correction (human feedback)
- Training data management
- Accuracy metrics
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.document import Document
from app.models.extraction import (
    DocumentExtraction,
    ExtractionCorrection,
    TrainingSample,
    ExtractionAccuracyMetric,
    ExtractionPattern,
    ExtractionConfidenceLevel,
    ExtractionStatus,
    CorrectionType
)
from app.services.intelligent_extractor import (
    intelligent_extractor,
    feedback_manager,
    training_collector,
    DocumentType,
    ConfidenceLevel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extraction", tags=["Document Extraction"])


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class ExtractionRequest(BaseModel):
    """Request to extract data from a document."""
    document_id: int = Field(..., description="ID of the document to extract from")
    document_type: Optional[str] = Field(None, description="Known document type (optional)")
    use_rag: bool = Field(True, description="Whether to use RAG enhancement")


class ExtractionResponse(BaseModel):
    """Response containing extraction results."""
    success: bool
    extraction_id: Optional[int]
    document_type: str
    type_confidence: float
    status: str
    overall_confidence: float
    confidence_level: str
    completeness_score: float
    fields_requiring_review: List[str]
    extracted_data: Dict[str, Any]
    validation: Dict[str, Any]
    processing_time_ms: float
    rag_context_used: bool
    similar_documents_found: int


class DocumentTypeRequest(BaseModel):
    """Request to detect document type."""
    text: str = Field(..., min_length=50, description="Document text content")


class DocumentTypeResponse(BaseModel):
    """Response containing document type detection."""
    detected_type: str
    confidence: float
    confidence_level: str
    matched_keywords: List[str]
    matched_sections: List[str]
    alternative_types: List[Dict[str, Any]]


class CorrectionRequest(BaseModel):
    """Request to submit an extraction correction."""
    extraction_id: int = Field(..., description="ID of the extraction to correct")
    field_name: str = Field(..., description="Name of the field being corrected")
    field_path: Optional[str] = Field(None, description="Full path for nested fields")
    original_value: Optional[Any] = Field(None, description="Original extracted value")
    corrected_value: Any = Field(..., description="Corrected value")
    correction_reason: Optional[str] = Field(None, description="Optional reason for correction")


class CorrectionResponse(BaseModel):
    """Response confirming correction."""
    success: bool
    correction_id: int
    correction_type: str
    message: str


class AccuracyMetricsResponse(BaseModel):
    """Response containing accuracy metrics."""
    field_name: Optional[str]
    document_type: Optional[str]
    period_days: int
    total_extractions: int
    total_corrections: int
    accuracy_rate: float
    correction_breakdown: Dict[str, int]
    confidence_distribution: Dict[str, int]


class TrainingDataExportRequest(BaseModel):
    """Request to export training data."""
    format: str = Field("jsonl", description="Export format: jsonl, csv, huggingface")
    include_only_verified: bool = Field(False, description="Only include verified samples")
    min_confidence: float = Field(0.0, ge=0.0, le=100.0, description="Minimum confidence threshold")


class TrainingDataExportResponse(BaseModel):
    """Response containing export information."""
    success: bool
    export_path: str
    sample_count: int
    message: str


class TrainingStatsResponse(BaseModel):
    """Response containing training data statistics."""
    total_samples: int
    verified_samples: int
    verification_rate: float
    document_type_distribution: Dict[str, int]
    average_confidence: float
    output_directory: str


# =============================================================================
# EXTRACTION ENDPOINTS
# =============================================================================

@router.post("/extract", response_model=ExtractionResponse)
async def extract_document(
    request: ExtractionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    # current_user = Depends(get_current_user),  # Add auth dependency
):
    """
    Extract structured data from a document.

    This endpoint:
    1. Detects the document type (if not provided)
    2. Extracts all relevant fields using intelligent patterns
    3. Validates extraction against template requirements
    4. Calculates confidence scores for each field
    5. Stores results in database

    Fields with confidence < 70% are flagged for manual review.
    """
    # Get document from database
    query = select(Document).where(Document.id == request.document_id)
    result = await db.execute(query)
    document = result.scalars().first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {request.document_id} not found"
        )

    if not document.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no file path"
        )

    try:
        # Perform extraction
        extraction_result = await intelligent_extractor.extract_from_document(
            file_path=document.file_path,
            document_type=request.document_type,
            document_id=request.document_id,
            use_rag=request.use_rag
        )

        # Store extraction in database
        db_extraction = DocumentExtraction(
            document_id=request.document_id,
            detected_type=extraction_result.document_type.detected_type.value,
            type_confidence=extraction_result.document_type.confidence,
            type_confidence_level=ExtractionConfidenceLevel(extraction_result.document_type.confidence_level.value),
            matched_keywords=extraction_result.document_type.matched_keywords,
            matched_sections=extraction_result.document_type.matched_sections,
            status=ExtractionStatus(extraction_result.status.value),
            extracted_data=extraction_result.to_dict()["extracted_data"],
            is_valid=extraction_result.validation.is_valid,
            completeness_score=extraction_result.validation.completeness_score,
            required_fields_found=extraction_result.validation.required_fields_found,
            required_fields_missing=extraction_result.validation.required_fields_missing,
            validation_errors=extraction_result.validation.errors,
            validation_warnings=extraction_result.validation.warnings,
            overall_confidence=extraction_result.overall_confidence,
            overall_confidence_level=ExtractionConfidenceLevel(extraction_result.overall_confidence_level.value),
            fields_requiring_review=extraction_result.fields_requiring_review,
            processing_time_ms=extraction_result.processing_time_ms,
            rag_context_used=extraction_result.rag_context_used,
            similar_documents_found=extraction_result.similar_documents_found,
            raw_text_hash=extraction_result.raw_text_hash,
        )

        db.add(db_extraction)
        await db.commit()
        await db.refresh(db_extraction)

        # Log training sample in background
        if document.ocr_text:
            background_tasks.add_task(
                training_collector.log_extraction,
                request.document_id,
                document.ocr_text,
                extraction_result
            )

        return ExtractionResponse(
            success=True,
            extraction_id=db_extraction.id,
            document_type=extraction_result.document_type.detected_type.value,
            type_confidence=extraction_result.document_type.confidence,
            status=extraction_result.status.value,
            overall_confidence=extraction_result.overall_confidence,
            confidence_level=extraction_result.overall_confidence_level.value,
            completeness_score=extraction_result.validation.completeness_score,
            fields_requiring_review=extraction_result.fields_requiring_review,
            extracted_data=extraction_result.to_dict()["extracted_data"],
            validation=extraction_result.validation.to_dict(),
            processing_time_ms=extraction_result.processing_time_ms,
            rag_context_used=extraction_result.rag_context_used,
            similar_documents_found=extraction_result.similar_documents_found
        )

    except Exception as e:
        logger.error(f"Extraction error for document {request.document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )


@router.post("/detect-type", response_model=DocumentTypeResponse)
async def detect_document_type(request: DocumentTypeRequest):
    """
    Detect the type of an insurance document from text.

    This endpoint analyzes the text content to identify:
    - Document type (MRC slip, policy, endorsement, etc.)
    - Confidence level
    - Matched keywords and sections
    - Alternative possible types
    """
    try:
        result = await intelligent_extractor.detect_document_type(request.text)

        return DocumentTypeResponse(
            detected_type=result.detected_type.value,
            confidence=result.confidence,
            confidence_level=result.confidence_level.value,
            matched_keywords=result.matched_keywords,
            matched_sections=result.matched_sections,
            alternative_types=[
                {"type": t.value, "confidence": c}
                for t, c in result.alternative_types
            ]
        )

    except Exception as e:
        logger.error(f"Type detection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Type detection failed: {str(e)}"
        )


@router.get("/extraction/{extraction_id}")
async def get_extraction(
    extraction_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific extraction result by ID."""
    query = select(DocumentExtraction).where(DocumentExtraction.id == extraction_id)
    result = await db.execute(query)
    extraction = result.scalars().first()

    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction {extraction_id} not found"
        )

    return {
        "id": extraction.id,
        "document_id": extraction.document_id,
        "detected_type": extraction.detected_type,
        "type_confidence": extraction.type_confidence,
        "status": extraction.status.value,
        "overall_confidence": extraction.overall_confidence,
        "confidence_level": extraction.overall_confidence_level.value,
        "completeness_score": extraction.completeness_score,
        "is_valid": extraction.is_valid,
        "extracted_data": extraction.extracted_data,
        "fields_requiring_review": extraction.fields_requiring_review,
        "required_fields_found": extraction.required_fields_found,
        "required_fields_missing": extraction.required_fields_missing,
        "validation_errors": extraction.validation_errors,
        "validation_warnings": extraction.validation_warnings,
        "reviewed": extraction.reviewed,
        "created_at": extraction.created_at.isoformat(),
    }


@router.get("/document/{document_id}/extractions")
async def get_document_extractions(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all extractions for a specific document."""
    query = select(DocumentExtraction).where(
        DocumentExtraction.document_id == document_id
    ).order_by(DocumentExtraction.created_at.desc())

    result = await db.execute(query)
    extractions = result.scalars().all()

    return {
        "document_id": document_id,
        "total_extractions": len(extractions),
        "extractions": [
            {
                "id": e.id,
                "detected_type": e.detected_type,
                "status": e.status.value,
                "overall_confidence": e.overall_confidence,
                "completeness_score": e.completeness_score,
                "reviewed": e.reviewed,
                "created_at": e.created_at.isoformat(),
            }
            for e in extractions
        ]
    }


# =============================================================================
# CORRECTION ENDPOINTS (HUMAN FEEDBACK)
# =============================================================================

@router.post("/correction", response_model=CorrectionResponse)
async def submit_correction(
    request: CorrectionRequest,
    db: AsyncSession = Depends(get_db),
    # current_user = Depends(get_current_user),  # Add auth dependency
):
    """
    Submit a correction for an extracted field.

    This endpoint allows humans to correct extraction errors,
    which helps improve future extractions through:
    - Pattern refinement
    - Training data collection
    - Accuracy tracking
    """
    # Get extraction
    query = select(DocumentExtraction).where(DocumentExtraction.id == request.extraction_id)
    result = await db.execute(query)
    extraction = result.scalars().first()

    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction {request.extraction_id} not found"
        )

    # Determine correction type
    if request.original_value is None:
        correction_type = CorrectionType.MISSING_VALUE
    elif request.corrected_value is None:
        correction_type = CorrectionType.FALSE_POSITIVE
    elif isinstance(request.original_value, str) and isinstance(request.corrected_value, str):
        if request.original_value.lower() == request.corrected_value.lower():
            correction_type = CorrectionType.FORMATTING
        else:
            correction_type = CorrectionType.WRONG_VALUE
    else:
        correction_type = CorrectionType.WRONG_VALUE

    # Get original confidence if available
    original_confidence = None
    if extraction.extracted_data:
        field_data = extraction.extracted_data.get(request.field_name, {})
        if isinstance(field_data, dict):
            original_confidence = field_data.get("confidence")

    # Create correction record
    correction = ExtractionCorrection(
        extraction_id=request.extraction_id,
        field_name=request.field_name,
        field_path=request.field_path,
        original_value=request.original_value,
        corrected_value=request.corrected_value,
        original_confidence=original_confidence,
        correction_type=correction_type,
        correction_reason=request.correction_reason,
        corrected_by=1,  # Replace with current_user.id
    )

    db.add(correction)
    await db.commit()
    await db.refresh(correction)

    return CorrectionResponse(
        success=True,
        correction_id=correction.id,
        correction_type=correction_type.value,
        message=f"Correction recorded for field '{request.field_name}'"
    )


@router.get("/extraction/{extraction_id}/corrections")
async def get_extraction_corrections(
    extraction_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all corrections for a specific extraction."""
    query = select(ExtractionCorrection).where(
        ExtractionCorrection.extraction_id == extraction_id
    ).order_by(ExtractionCorrection.created_at.desc())

    result = await db.execute(query)
    corrections = result.scalars().all()

    return {
        "extraction_id": extraction_id,
        "total_corrections": len(corrections),
        "corrections": [
            {
                "id": c.id,
                "field_name": c.field_name,
                "original_value": c.original_value,
                "corrected_value": c.corrected_value,
                "correction_type": c.correction_type.value,
                "correction_reason": c.correction_reason,
                "created_at": c.created_at.isoformat(),
            }
            for c in corrections
        ]
    }


@router.post("/extraction/{extraction_id}/mark-reviewed")
async def mark_extraction_reviewed(
    extraction_id: int,
    db: AsyncSession = Depends(get_db),
    # current_user = Depends(get_current_user),
):
    """Mark an extraction as reviewed by a human."""
    query = select(DocumentExtraction).where(DocumentExtraction.id == extraction_id)
    result = await db.execute(query)
    extraction = result.scalars().first()

    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction {extraction_id} not found"
        )

    extraction.mark_reviewed(user_id=1)  # Replace with current_user.id
    await db.commit()

    return {"success": True, "message": "Extraction marked as reviewed"}


# =============================================================================
# ACCURACY METRICS ENDPOINTS
# =============================================================================

@router.get("/metrics/accuracy", response_model=AccuracyMetricsResponse)
async def get_accuracy_metrics(
    field_name: Optional[str] = Query(None, description="Filter by field name"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get extraction accuracy metrics.

    Provides:
    - Overall accuracy rate
    - Correction type breakdown
    - Confidence distribution
    """
    period_start = datetime.now(timezone.utc) - timedelta(days=days)

    # Query extractions
    extraction_query = select(func.count(DocumentExtraction.id)).where(
        DocumentExtraction.created_at >= period_start
    )
    if document_type:
        extraction_query = extraction_query.where(
            DocumentExtraction.detected_type == document_type
        )

    extraction_result = await db.execute(extraction_query)
    total_extractions = extraction_result.scalar() or 0

    # Query corrections
    correction_query = select(ExtractionCorrection).where(
        ExtractionCorrection.created_at >= period_start
    )
    if field_name:
        correction_query = correction_query.where(
            ExtractionCorrection.field_name == field_name
        )

    correction_result = await db.execute(correction_query)
    corrections = correction_result.scalars().all()

    # Calculate metrics
    total_corrections = len(corrections)
    accuracy_rate = (total_extractions - total_corrections) / total_extractions if total_extractions > 0 else 0.0

    # Correction type breakdown
    correction_breakdown = {
        "missing_value": 0,
        "false_positive": 0,
        "wrong_value": 0,
        "formatting": 0,
        "type_mismatch": 0,
    }
    for c in corrections:
        if c.correction_type.value in correction_breakdown:
            correction_breakdown[c.correction_type.value] += 1

    # Confidence distribution query
    conf_query = select(DocumentExtraction.overall_confidence_level, func.count()).where(
        DocumentExtraction.created_at >= period_start
    ).group_by(DocumentExtraction.overall_confidence_level)

    conf_result = await db.execute(conf_query)
    conf_rows = conf_result.all()

    confidence_distribution = {"high": 0, "medium": 0, "low": 0}
    for level, count in conf_rows:
        if level:
            confidence_distribution[level.value] = count

    return AccuracyMetricsResponse(
        field_name=field_name,
        document_type=document_type,
        period_days=days,
        total_extractions=total_extractions,
        total_corrections=total_corrections,
        accuracy_rate=accuracy_rate,
        correction_breakdown=correction_breakdown,
        confidence_distribution=confidence_distribution
    )


@router.get("/metrics/fields")
async def get_field_accuracy(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    limit: int = Query(20, ge=1, le=100, description="Number of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get accuracy metrics broken down by field.

    Returns fields ordered by number of corrections (most problematic first).
    """
    period_start = datetime.now(timezone.utc) - timedelta(days=days)

    query = select(
        ExtractionCorrection.field_name,
        func.count(ExtractionCorrection.id).label("correction_count")
    ).where(
        ExtractionCorrection.created_at >= period_start
    ).group_by(
        ExtractionCorrection.field_name
    ).order_by(
        func.count(ExtractionCorrection.id).desc()
    ).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    return {
        "period_days": days,
        "fields": [
            {"field_name": field_name, "correction_count": count}
            for field_name, count in rows
        ]
    }


# =============================================================================
# TRAINING DATA ENDPOINTS
# =============================================================================

@router.post("/training/export", response_model=TrainingDataExportResponse)
async def export_training_data(request: TrainingDataExportRequest):
    """
    Export training data in specified format.

    Supported formats:
    - jsonl: JSON Lines format
    - csv: CSV with flattened data
    - huggingface: Format compatible with Hugging Face datasets
    """
    try:
        export_path = await training_collector.export_training_dataset(
            format=request.format,
            include_only_verified=request.include_only_verified,
            min_confidence=request.min_confidence
        )

        if not export_path:
            return TrainingDataExportResponse(
                success=False,
                export_path="",
                sample_count=0,
                message="No samples found matching criteria"
            )

        # Get sample count
        stats = training_collector.get_statistics()

        return TrainingDataExportResponse(
            success=True,
            export_path=export_path,
            sample_count=stats["total_samples"],
            message=f"Exported {stats['total_samples']} samples to {export_path}"
        )

    except Exception as e:
        logger.error(f"Training data export error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


@router.get("/training/stats", response_model=TrainingStatsResponse)
async def get_training_stats():
    """Get statistics about collected training data."""
    stats = training_collector.get_statistics()

    return TrainingStatsResponse(
        total_samples=stats["total_samples"],
        verified_samples=stats["verified_samples"],
        verification_rate=stats["verification_rate"],
        document_type_distribution=stats["document_type_distribution"],
        average_confidence=stats["average_confidence"],
        output_directory=stats["output_directory"]
    )


@router.post("/training/samples/{sample_id}/verify")
async def verify_training_sample(
    sample_id: str,
    ground_truth: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a training sample with ground truth data.

    This marks the sample as verified for high-quality training.
    """
    query = select(TrainingSample).where(TrainingSample.sample_id == sample_id)
    result = await db.execute(query)
    sample = result.scalars().first()

    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training sample {sample_id} not found"
        )

    sample.ground_truth = ground_truth
    sample.has_ground_truth = True
    sample.quality_score = 1.0  # Verified samples get max quality

    await db.commit()

    return {
        "success": True,
        "sample_id": sample_id,
        "message": "Sample verified with ground truth"
    }


# =============================================================================
# PATTERN MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/patterns")
async def list_patterns(
    field_name: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    is_active: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """List extraction patterns with their performance metrics."""
    query = select(ExtractionPattern).where(ExtractionPattern.is_active == is_active)

    if field_name:
        query = query.where(ExtractionPattern.field_name == field_name)
    if document_type:
        query = query.where(ExtractionPattern.document_type == document_type)

    query = query.order_by(ExtractionPattern.priority.desc(), ExtractionPattern.accuracy_rate.desc())

    result = await db.execute(query)
    patterns = result.scalars().all()

    return {
        "total": len(patterns),
        "patterns": [
            {
                "id": p.id,
                "field_name": p.field_name,
                "document_type": p.document_type,
                "pattern_regex": p.pattern_regex,
                "description": p.description,
                "times_used": p.times_used,
                "accuracy_rate": p.accuracy_rate,
                "priority": p.priority,
                "is_active": p.is_active,
            }
            for p in patterns
        ]
    }


@router.post("/patterns")
async def create_pattern(
    field_name: str,
    pattern_regex: str,
    document_type: Optional[str] = None,
    description: Optional[str] = None,
    priority: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Create a new extraction pattern."""
    import re

    # Validate regex
    try:
        re.compile(pattern_regex)
    except re.error as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid regex pattern: {e}"
        )

    pattern = ExtractionPattern(
        field_name=field_name,
        document_type=document_type,
        pattern_regex=pattern_regex,
        description=description,
        priority=priority,
        source="manual",
        created_by=1,  # Replace with current_user.id
    )

    db.add(pattern)
    await db.commit()
    await db.refresh(pattern)

    return {
        "success": True,
        "pattern_id": pattern.id,
        "message": f"Pattern created for field '{field_name}'"
    }


# =============================================================================
# BULK OPERATIONS
# =============================================================================

@router.post("/bulk/extract")
async def bulk_extract(
    document_ids: List[int],
    background_tasks: BackgroundTasks,
    document_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Queue multiple documents for extraction.

    Extractions are processed in the background.
    """
    # Validate documents exist
    query = select(Document.id).where(Document.id.in_(document_ids))
    result = await db.execute(query)
    found_ids = set(row[0] for row in result.all())

    missing_ids = set(document_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documents not found: {list(missing_ids)}"
        )

    # Queue extractions
    for doc_id in document_ids:
        background_tasks.add_task(
            _process_extraction_background,
            doc_id,
            document_type
        )

    return {
        "success": True,
        "queued_count": len(document_ids),
        "message": f"Queued {len(document_ids)} documents for extraction"
    }


async def _process_extraction_background(document_id: int, document_type: Optional[str]):
    """Background task for processing extractions."""
    # This would need proper database session management for background tasks
    logger.info(f"Processing extraction for document {document_id} in background")
