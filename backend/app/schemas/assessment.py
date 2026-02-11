"""
InstantRisk V2 - Assessment Pydantic Schemas

This module defines Pydantic schemas for assessment-related
CRUD operations and API responses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.models.assessment import AssessmentStatus, AssessmentDecision, RiskCategory


class AssessmentBase(BaseModel):
    """Base schema with common assessment fields."""
    title: str = Field(..., min_length=5, max_length=500)
    description: Optional[str] = None
    risk_category: RiskCategory = RiskCategory.PROPERTY


class AssessmentCreate(AssessmentBase):
    """
    Schema for creating a new assessment.

    Attributes:
        title: Title or summary of the risk.
        description: Detailed description of the risk.
        risk_category: Category of the risk.
        syndicate_id: Target syndicate for the assessment.
        insured_name: Name of the insured party.
        broker_reference: Broker's reference number.
        premium: Quoted premium amount.
        sum_insured: Total sum insured.
        deductible: Deductible amount.
        inception_date: Policy inception date.
        expiry_date: Policy expiry date.
        territory: Primary territory/region.
        exposure_details: Additional exposure information.
    """
    syndicate_id: Optional[int] = None
    insured_name: Optional[str] = Field(None, max_length=255)
    broker_reference: Optional[str] = Field(None, max_length=100)
    premium: Optional[float] = Field(None, ge=0)
    sum_insured: Optional[float] = Field(None, ge=0)
    deductible: Optional[float] = Field(None, ge=0)
    inception_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    territory: Optional[str] = Field(None, max_length=100)
    exposure_details: Optional[Dict[str, Any]] = None


class AssessmentUpdate(BaseModel):
    """
    Schema for updating an existing assessment.

    All fields are optional to allow partial updates.
    """
    title: Optional[str] = Field(None, min_length=5, max_length=500)
    description: Optional[str] = None
    risk_category: Optional[RiskCategory] = None
    syndicate_id: Optional[int] = None
    insured_name: Optional[str] = Field(None, max_length=255)
    broker_reference: Optional[str] = Field(None, max_length=100)
    premium: Optional[float] = Field(None, ge=0)
    sum_insured: Optional[float] = Field(None, ge=0)
    deductible: Optional[float] = Field(None, ge=0)
    inception_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    territory: Optional[str] = Field(None, max_length=100)
    exposure_details: Optional[Dict[str, Any]] = None
    underwriter_notes: Optional[str] = None
    is_flagged: Optional[bool] = None
    flag_reason: Optional[str] = Field(None, max_length=255)


class AssessmentDecisionUpdate(BaseModel):
    """
    Schema for updating assessment decision.

    Attributes:
        decision: The GO/NO-GO/REFER decision.
        decision_rationale: Explanation for the decision.
    """
    decision: AssessmentDecision
    decision_rationale: str = Field(..., min_length=10, max_length=2000)


class AIAnalysisResponse(BaseModel):
    """
    Schema for AI analysis results.

    Attributes:
        risk_score: Calculated risk score (0-100).
        confidence_score: AI confidence level (0-100).
        risk_factors: List of identified risk factors.
        recommendations: AI-generated recommendations.
        summary: Brief summary of the analysis.
    """
    risk_score: int = Field(..., ge=0, le=100)
    confidence_score: int = Field(..., ge=0, le=100)
    risk_factors: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    summary: str


class AssessmentResponse(AssessmentBase):
    """
    Schema for assessment response data.

    Includes all assessment fields and related data.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID  # EC2 database uses UUID for assessment IDs
    reference_number: Optional[str] = None  # May not exist in EC2 database
    status: AssessmentStatus
    decision: AssessmentDecision
    created_by: UUID
    syndicate_id: Optional[int] = None
    insured_name: Optional[str] = None
    broker_reference: Optional[str] = None
    premium: Optional[float] = None
    sum_insured: Optional[float] = None
    deductible: Optional[float] = None
    inception_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    territory: Optional[str] = None
    exposure_details: Optional[Dict[str, Any]] = None
    risk_score: Optional[int] = None
    confidence_score: Optional[int] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    ai_recommendations: Optional[List[Any]] = None  # Can be List[str] or List[Dict]
    underwriter_notes: Optional[str] = None
    decision_rationale: Optional[str] = None
    ocr_extracted_text: Optional[str] = None
    is_flagged: bool = False
    flag_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    # Computed fields
    risk_rating: Optional[str] = None


class AssessmentListResponse(BaseModel):
    """
    Schema for paginated assessment list response.

    Attributes:
        items: List of assessments.
        total: Total number of assessments.
        page: Current page number.
        page_size: Number of items per page.
        pages: Total number of pages.
    """
    items: List[AssessmentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AssessmentSummary(BaseModel):
    """
    Schema for assessment summary statistics.

    Attributes:
        total_assessments: Total number of assessments.
        pending_count: Number of pending assessments.
        completed_count: Number of completed assessments.
        go_decisions: Number of GO decisions.
        no_go_decisions: Number of NO-GO decisions.
        refer_decisions: Number of REFER decisions.
        average_risk_score: Average risk score across assessments.
    """
    total_assessments: int
    pending_count: int
    completed_count: int
    go_decisions: int
    no_go_decisions: int
    refer_decisions: int
    average_risk_score: Optional[float] = None
