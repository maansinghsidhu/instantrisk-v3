"""
Vision Analysis Schemas

Request/Response models for computer vision property inspection.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class RiskFactor(BaseModel):
    """Individual risk factor identified in property inspection."""
    category: str = Field(..., description="Risk category: roof, fire, structural, security, environmental")
    severity: str = Field(..., description="Severity: low, medium, high, critical")
    description: str = Field(..., description="Detailed observation")
    recommendation: Optional[str] = Field(None, description="Mitigation advice")


class VisionAnalysisResult(BaseModel):
    """Property vision analysis result."""
    risk_score: int = Field(..., description="Risk score 0-100 (higher = riskier)", ge=0, le=100)
    risk_factors: List[RiskFactor] = Field(default_factory=list)
    overall_assessment: str = Field(..., description="Summary of findings")
    insurability: Optional[str] = Field(None, description="excellent, good, acceptable, marginal, uninsurable")
    key_concerns: List[str] = Field(default_factory=list, description="Top 3-5 concerns")
    image_count: Optional[int] = Field(None, description="Number of images analyzed")
    raw_response: Optional[str] = Field(None, description="Raw model response (debug)")
    error: Optional[str] = Field(None, description="Error message if analysis failed")


class VisionAnalysisRequest(BaseModel):
    """Request for property vision analysis."""
    assessment_id: UUID = Field(..., description="Assessment to attach analysis to")
    additional_context: Optional[str] = Field(None, description="Additional context (address, property type, etc.)")


class PropertyReportResponse(BaseModel):
    """Stored property analysis report."""
    assessment_id: UUID
    property_analysis: Optional[Dict[str, Any]] = Field(None, description="Vision analysis results")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
