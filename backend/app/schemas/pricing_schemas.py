"""
Pricing and Quote Schemas

Request/Response models for pricing and quote management.
Extracted from lloyds.py for global underwriter platform.
"""

from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List, Any
from uuid import UUID

from pydantic import BaseModel, Field


class PricingRequest(BaseModel):
    """Request for technical pricing."""
    assessment_id: UUID
    class_of_business: str
    limit_of_liability: Decimal
    currency: str = "GBP"
    deductible: Optional[Decimal] = None
    territory: Optional[str] = None


class PricingResponse(BaseModel):
    """Technical pricing result."""
    assessment_id: UUID
    technical_premium: Decimal
    currency: str
    risk_score: float = Field(..., description="Risk score 0-100")
    risk_category: str = Field(..., description="low, medium, high, very_high")
    confidence_low: Decimal
    confidence_high: Decimal
    loading_factors: Dict[str, float]
    key_drivers: List[str]
    explanation: str


class QuoteCreate(BaseModel):
    """Request to generate a formal quote."""
    pricing_result_id: int
    quoted_premium: Decimal
    quoted_line: Optional[Decimal] = Field(
        None,
        description="Offered line percentage"
    )
    terms: Dict[str, Any] = Field(default_factory=dict)
    conditions: List[str] = Field(default_factory=list)
    subjectivities: List[str] = Field(
        default_factory=list,
        description="Conditions precedent to attachment"
    )
    exclusions: List[str] = Field(default_factory=list)
    valid_days: int = Field(14, description="Quote validity in days")


class QuoteResponse(BaseModel):
    """Generated quote details."""
    id: int
    quote_reference: str
    assessment_id: UUID
    quoted_premium: Decimal
    quoted_line: Optional[Decimal]
    currency: str
    terms: Dict[str, Any]
    conditions: List[str]
    subjectivities: List[str]
    exclusions: List[str]
    valid_from: datetime
    valid_until: datetime
    status: str = Field(
        ...,
        description="draft, issued, accepted, declined, expired"
    )
    created_at: datetime
    issued_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
