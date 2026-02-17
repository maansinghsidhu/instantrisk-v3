"""
InstantRisk - Computer Vision Property Inspection Router

Endpoints for analyzing property photos using AWS Bedrock vision models.
"""

import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.services.vision_inspector import get_vision_inspector
from app.schemas.vision import (
    VisionAnalysisResult,
    VisionAnalysisRequest,
    PropertyReportResponse
)

# Security imports
from app.utils import validate_file, FileValidationError, sanitize_filename
import tempfile
import os

logger = logging.getLogger("vision")

router = APIRouter()


@router.post("/analyze-property", response_model=VisionAnalysisResult)
async def analyze_property_image(
    file: UploadFile = File(..., description="Property image to analyze"),
    assessment_id: str = Form(..., description="Assessment UUID"),
    additional_context: Optional[str] = Form(None, description="Additional context"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> VisionAnalysisResult:
    """
    Analyze a property image for risk factors using computer vision.

    Upload a property photo and receive:
    - Risk score (0-100)
    - Detailed risk factors by category
    - Overall assessment and insurability rating
    - Recommendations for risk mitigation

    The analysis is automatically stored in the assessment's property_analysis field.
    """
    # Validate assessment exists and user has access
    try:
        assessment_uuid = UUID(assessment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid assessment ID format"
        )

    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_uuid)
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )

    # Check user has access (owner or admin)
    if assessment.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Validate file is an image
    safe_filename = sanitize_filename(file.filename)
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    file_ext = Path(safe_filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
        )

    # Read file content
    content = await file.read()

    # Validate file size (max 10MB for images)
    max_size = 10 * 1024 * 1024  # 10MB
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {max_size // (1024 * 1024)}MB"
        )

    # Basic security validation
    try:
        await validate_file(content, safe_filename)
    except FileValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File validation failed: {e.message}"
        )

    # Save to temporary file for processing
    temp_file = None
    try:
        # Create temp file with proper extension
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_ext,
            prefix="vision_"
        )
        temp_file.write(content)
        temp_file.close()

        # Analyze the image
        vision_inspector = get_vision_inspector()
        analysis_result = await vision_inspector.analyze_property_image(
            image_path=temp_file.name,
            additional_context=additional_context
        )

        # Store results in assessment
        assessment.property_analysis = analysis_result
        await db.commit()

        logger.info(
            f"Vision analysis completed for assessment {assessment_id}: "
            f"risk_score={analysis_result.get('risk_score', 'N/A')}"
        )

        # Return structured response
        return VisionAnalysisResult(**analysis_result)

    except Exception as e:
        logger.error(f"Vision analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )

    finally:
        # Clean up temp file
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")


@router.get("/property-report/{assessment_id}", response_model=PropertyReportResponse)
async def get_property_report(
    assessment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> PropertyReportResponse:
    """
    Get the stored property vision analysis for an assessment.

    Returns the complete vision analysis results including risk score,
    risk factors, and recommendations.
    """
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )

    # Check user has access
    if assessment.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return PropertyReportResponse(
        assessment_id=assessment.id,
        property_analysis=assessment.property_analysis,
        created_at=assessment.created_at,
        updated_at=assessment.updated_at
    )
