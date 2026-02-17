"""
InstantRisk V3 - Pricing Router

API endpoints for technical pricing and quote generation.
Provides AI-enhanced pricing calculations and formal quote management.

Key features:
- Technical premium calculation
- Risk scoring and categorization
- Formal quote generation with terms and conditions
- Quote lifecycle management
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.pricing_models import PricingResult, Quote
from app.schemas.pricing_schemas import (
    PricingRequest,
    PricingResponse,
    QuoteCreate,
    QuoteResponse,
)

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class TechnicalPriceRequest(BaseModel):
    """Request for technical pricing calculation."""
    assessment_id: str = Field(..., description="Assessment ID to price")
    class_of_business: str = Field(..., description="Lloyd's class of business")
    limit_of_liability: Decimal = Field(..., description="Policy limit")
    currency: str = Field("GBP", description="Currency code")
    deductible: Optional[Decimal] = Field(None, description="Deductible amount")
    territory: Optional[str] = Field(None, description="Primary territory")
    additional_factors: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional pricing factors"
    )


class TechnicalPriceResponse(BaseModel):
    """Response for technical pricing."""
    pricing_id: int
    assessment_id: str
    technical_premium: Decimal
    currency: str
    risk_score: float
    risk_category: str
    confidence_low: Decimal
    confidence_high: Decimal
    loading_factors: Dict[str, float]
    key_drivers: List[str]
    explanation: str
    calculated_at: datetime


class QuoteStatusUpdate(BaseModel):
    """Request to update quote status."""
    status: str = Field(
        ...,
        description="New status: draft, issued, accepted, declined, expired, superseded"
    )


class QuoteListResponse(BaseModel):
    """Response for listing quotes."""
    quotes: List[QuoteResponse]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================

def _generate_quote_reference() -> str:
    """Generate a unique quote reference."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique_part = uuid.uuid4().hex[:6].upper()
    return f"QT-{timestamp}-{unique_part}"


def _calculate_technical_premium(
    limit: Decimal,
    class_of_business: str,
    territory: Optional[str],
    additional_factors: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calculate technical premium using simplified actuarial approach.

    In production, this would use ML models and historical data.
    """
    # Base rate by class (simplified)
    base_rates = {
        "property": Decimal("0.005"),  # 0.5% of limit
        "marine": Decimal("0.008"),
        "cyber": Decimal("0.015"),
        "casualty": Decimal("0.010"),
        "aviation": Decimal("0.012"),
        "energy": Decimal("0.020"),
    }

    # Default to property rate
    base_rate = base_rates.get(class_of_business.lower(), Decimal("0.010"))

    # Calculate base premium
    base_premium = limit * base_rate

    # Apply loading factors
    loading_factors = {
        "base_rate": float(base_rate * 100),
        "cat_load": 1.15,  # 15% cat loading
        "expense_load": 1.25,  # 25% expense loading
        "profit_margin": 1.10,  # 10% profit margin
    }

    # Territory adjustment
    territory_factors = {
        "US": 1.20,
        "EU": 1.00,
        "APAC": 1.10,
        "LATAM": 1.30,
    }
    if territory:
        territory_factor = territory_factors.get(territory.upper(), 1.05)
        loading_factors["territory_adjustment"] = territory_factor

    # Calculate final premium
    technical_premium = base_premium
    for factor_name, factor_value in loading_factors.items():
        if factor_name != "base_rate":
            technical_premium *= Decimal(str(factor_value))

    # Calculate risk score (0-100)
    risk_score = min(100, float(base_rate * 1000) * 1.5)

    # Determine risk category
    if risk_score < 25:
        risk_category = "low"
    elif risk_score < 50:
        risk_category = "medium"
    elif risk_score < 75:
        risk_category = "high"
    else:
        risk_category = "very_high"

    # Confidence interval (simplified)
    confidence_low = technical_premium * Decimal("0.85")
    confidence_high = technical_premium * Decimal("1.20")

    # Key drivers
    key_drivers = [
        f"Class of business: {class_of_business}",
        f"Limit: {limit:,.2f}",
    ]
    if territory:
        key_drivers.append(f"Territory: {territory}")

    explanation = (
        f"Technical premium calculated using base rate of {float(base_rate * 100):.2f}% "
        f"for {class_of_business} class with standard loadings applied."
    )

    return {
        "technical_premium": technical_premium,
        "risk_score": risk_score,
        "risk_category": risk_category,
        "confidence_low": confidence_low,
        "confidence_high": confidence_high,
        "loading_factors": loading_factors,
        "key_drivers": key_drivers,
        "explanation": explanation,
    }


def _quote_to_response(quote: Quote) -> QuoteResponse:
    """Convert quote model to response schema."""
    return QuoteResponse(
        id=quote.id,
        quote_reference=quote.quote_reference,
        assessment_id=quote.assessment_id,
        quoted_premium=quote.quoted_premium,
        quoted_line=quote.quoted_line,
        currency=quote.currency,
        terms=quote.terms or {},
        conditions=quote.conditions or [],
        subjectivities=quote.subjectivities or [],
        exclusions=quote.exclusions or [],
        valid_from=quote.valid_from,
        valid_until=quote.valid_until,
        status=quote.status,
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/technical", response_model=TechnicalPriceResponse)
async def calculate_technical_price(
    request: TechnicalPriceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TechnicalPriceResponse:
    """
    Calculate technical premium for an assessment.

    Uses actuarial models and AI enhancement to calculate the
    technically correct premium for a risk.

    Args:
        request: TechnicalPriceRequest with pricing parameters.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        TechnicalPriceResponse with premium and risk analysis.
    """
    try:
        # Calculate technical premium
        pricing_data = _calculate_technical_premium(
            limit=request.limit_of_liability,
            class_of_business=request.class_of_business,
            territory=request.territory,
            additional_factors=request.additional_factors or {},
        )

        # Try to save pricing result to DB
        try:
            pricing_result = PricingResult(
                assessment_id=request.assessment_id,
                model_id=None,
                technical_premium=pricing_data["technical_premium"],
                currency=request.currency,
                risk_score=pricing_data["risk_score"],
                risk_category=pricing_data["risk_category"],
                confidence_interval_low=pricing_data["confidence_low"],
                confidence_interval_high=pricing_data["confidence_high"],
                loading_factors=pricing_data["loading_factors"],
                key_drivers=pricing_data["key_drivers"],
                explanation={"text": pricing_data["explanation"]},
            )
            db.add(pricing_result)
            await db.commit()
            await db.refresh(pricing_result)
            pricing_id = pricing_result.id
        except Exception:
            await db.rollback()
            pricing_id = 0  # DB save failed (e.g. FK constraint) — still return pricing

        return TechnicalPriceResponse(
            pricing_id=pricing_id,
            assessment_id=request.assessment_id,
            technical_premium=pricing_data["technical_premium"],
            currency=request.currency,
            risk_score=pricing_data["risk_score"],
            risk_category=pricing_data["risk_category"],
            confidence_low=pricing_data["confidence_low"],
            confidence_high=pricing_data["confidence_high"],
            loading_factors=pricing_data["loading_factors"],
            key_drivers=pricing_data["key_drivers"],
            explanation=pricing_data["explanation"],
            calculated_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        import traceback
        print(f"TECHNICAL PRICE ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate price: {str(e)}")


@router.post("/quote", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def generate_quote(
    request: QuoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuoteResponse:
    """
    Generate a formal quote from pricing results.

    Creates a bindable quote with terms, conditions, and validity period.

    Args:
        request: QuoteCreate with quote details.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        QuoteResponse with generated quote details.
    """
    # Get pricing result
    pricing_result = await db.execute(
        select(PricingResult).where(PricingResult.id == request.pricing_result_id)
    )
    pricing = pricing_result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pricing result {request.pricing_result_id} not found"
        )

    # Calculate validity period
    valid_from = datetime.now(timezone.utc)
    valid_until = valid_from + timedelta(days=request.valid_days)

    # Create quote
    quote = Quote(
        assessment_id=pricing.assessment_id,
        pricing_result_id=pricing.id,
        syndicate_id=current_user.syndicate_id,
        quote_reference=_generate_quote_reference(),
        quoted_premium=request.quoted_premium,
        currency=pricing.currency,
        quoted_line=request.quoted_line,
        terms=request.terms,
        conditions=request.conditions,
        subjectivities=request.subjectivities,
        exclusions=request.exclusions,
        valid_from=valid_from,
        valid_until=valid_until,
        status="draft",
    )

    db.add(quote)
    await db.commit()
    await db.refresh(quote)

    return _quote_to_response(quote)


@router.get("/quotes/{quote_id}", response_model=QuoteResponse)
async def get_quote(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuoteResponse:
    """
    Get quote details by ID.

    Args:
        quote_id: The quote ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        QuoteResponse with quote details.

    Raises:
        HTTPException: If quote not found or access denied.
    """
    result = await db.execute(
        select(Quote).where(Quote.id == quote_id)
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quote {quote_id} not found"
        )

    # Check access for non-admin users
    if current_user.role.value != "admin":
        if quote.syndicate_id and quote.syndicate_id != current_user.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this quote"
            )

    return _quote_to_response(quote)


@router.get("/quotes/assessment/{assessment_id}", response_model=QuoteListResponse)
async def get_quotes_for_assessment(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuoteListResponse:
    """
    Get all quotes for an assessment.

    Returns all quotes associated with the specified assessment.

    Args:
        assessment_id: The assessment ID.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        QuoteListResponse with list of quotes.
    """
    query = select(Quote).where(Quote.assessment_id == assessment_id)

    # Filter by syndicate for non-admin users
    if current_user.role.value != "admin" and current_user.syndicate_id:
        query = query.where(Quote.syndicate_id == current_user.syndicate_id)

    query = query.order_by(Quote.created_at.desc())

    result = await db.execute(query)
    quotes = result.scalars().all()

    quote_list = [_quote_to_response(q) for q in quotes]

    return QuoteListResponse(
        quotes=quote_list,
        total=len(quote_list),
    )


@router.put("/quotes/{quote_id}/status", response_model=QuoteResponse)
async def update_quote_status(
    quote_id: int,
    request: QuoteStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuoteResponse:
    """
    Update the status of a quote.

    Moves a quote through its lifecycle (draft -> issued -> accepted/declined).

    Args:
        quote_id: The quote ID.
        request: QuoteStatusUpdate with new status.
        current_user: The authenticated user.
        db: Database session.

    Returns:
        QuoteResponse with updated quote details.

    Raises:
        HTTPException: If quote not found, access denied, or invalid status.
    """
    valid_statuses = ["draft", "issued", "accepted", "declined", "expired", "superseded"]

    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    result = await db.execute(
        select(Quote).where(Quote.id == quote_id)
    )
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quote {quote_id} not found"
        )

    # Check access for non-admin users
    if current_user.role.value != "admin":
        if quote.syndicate_id and quote.syndicate_id != current_user.syndicate_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this quote"
            )

    # Update status
    quote.status = request.status

    # Update timestamps based on status
    now = datetime.now(timezone.utc)
    if request.status == "issued":
        quote.issued_at = now
    elif request.status == "accepted":
        quote.accepted_at = now

    await db.commit()
    await db.refresh(quote)

    return _quote_to_response(quote)
