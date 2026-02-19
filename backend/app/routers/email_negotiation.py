"""
InstantRisk V2 - Email Negotiation Router

Endpoints for AI-powered email negotiation within underwriter parameters.

Routes:
    POST /api/v1/email-negotiation/analyze     - Analyze a broker counter-offer
    POST /api/v1/email-negotiation/generate     - Generate negotiation email
    GET  /api/v1/email-negotiation/templates     - Get email templates
    GET  /api/v1/email-negotiation/history       - Get negotiation history
"""

import logging
from typing import Optional, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User
from app.services.email_negotiation import (
    email_negotiation_service,
    NegotiationParameters,
    BrokerCounterOffer,
    NegotiationStrategy,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================


class CounterOfferRequest(BaseModel):
    premium_offered: float = Field(..., description="Broker's offered premium")
    deductible_offered: float = Field(50000, description="Broker's offered deductible")
    coverage_requested: float = Field(5000000, description="Coverage amount requested")
    validity_period: int = Field(30, description="Validity period in days")
    conditions: List[str] = Field(
        default_factory=list, description="Special conditions"
    )
    concessions_requested: List[str] = Field(
        default_factory=list, description="Requested concessions"
    )
    justification: str = Field("", description="Broker's justification")


class NegotiationParamsRequest(BaseModel):
    min_premium: float = Field(..., description="Minimum acceptable premium")
    max_premium: float = Field(..., description="Target/preferred premium")
    min_deductible: float = Field(25000, description="Lowest acceptable deductible")
    max_deductible: float = Field(100000, description="Preferred deductible")
    min_coverage: float = Field(1000000, description="Minimum coverage")
    max_coverage: float = Field(10000000, description="Maximum coverage")
    auto_accept_threshold: float = Field(
        0.05, description="Auto-accept if within this %"
    )
    escalation_threshold: float = Field(0.20, description="Escalate if outside this %")
    flexible_terms: List[str] = Field(default_factory=list)
    hard_lines: List[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    counter_offer: CounterOfferRequest
    parameters: NegotiationParamsRequest
    broker_name: str = Field("", description="Broker name for email personalization")
    insured_name: str = Field("", description="Insured entity name")
    insurance_line: str = Field("cyber", description="Line of business")


class GenerateEmailRequest(BaseModel):
    strategy: str = Field("flexible", description="Negotiation strategy")
    broker_name: str = Field(..., description="Broker name")
    insured_name: str = Field(..., description="Insured entity name")
    premium: float = Field(..., description="Premium to propose")
    deductible: float = Field(50000, description="Deductible to propose")
    coverage: float = Field(5000000, description="Coverage amount")
    tone: str = Field("professional", description="Email tone")
    key_points: List[str] = Field(
        default_factory=list, description="Key points to include"
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/analyze")
async def analyze_counter_offer(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    """Analyze a broker counter-offer and get recommended response strategy."""
    try:
        co = request.counter_offer
        p = request.parameters

        counter_offer = BrokerCounterOffer(
            premium_offered=Decimal(str(co.premium_offered)),
            deductible_offered=Decimal(str(co.deductible_offered)),
            coverage_requested=Decimal(str(co.coverage_requested)),
            validity_period=co.validity_period,
            conditions=co.conditions,
            concessions_requested=co.concessions_requested,
            justification=co.justification,
        )

        params = NegotiationParameters(
            min_premium=Decimal(str(p.min_premium)),
            max_premium=Decimal(str(p.max_premium)),
            min_deductible=Decimal(str(p.min_deductible)),
            max_deductible=Decimal(str(p.max_deductible)),
            min_coverage=Decimal(str(p.min_coverage)),
            max_coverage=Decimal(str(p.max_coverage)),
            auto_accept_threshold=Decimal(str(p.auto_accept_threshold)),
            escalation_threshold=Decimal(str(p.escalation_threshold)),
            flexible_terms=p.flexible_terms,
            hard_lines=p.hard_lines,
        )

        result = email_negotiation_service.analyze_counter_offer(counter_offer, params)

        return {
            "recommended_action": result.recommended_action.value,
            "outcome": result.outcome.value,
            "premium_recommendation": float(result.premium_recommendation),
            "deductible_recommendation": float(result.deductible_recommendation),
            "coverage_recommendation": float(result.coverage_recommendation),
            "response_strategy": result.response_strategy,
            "reasoning": result.reasoning,
            "next_steps": result.next_steps,
            "escalation_required": result.escalation_required,
            "escalation_reason": result.escalation_reason,
            "generated_email": result.generated_email,
            "confidence": result.confidence,
        }
    except Exception as e:
        logger.error(f"Error analyzing counter-offer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_email(
    request: GenerateEmailRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate a negotiation email based on strategy and parameters."""
    try:
        strategy_map = {
            "firm": NegotiationStrategy.FIRM,
            "flexible": NegotiationStrategy.FLEXIBLE,
            "compromise": NegotiationStrategy.COMPROMISE,
            "escalate": NegotiationStrategy.ESCALATE,
            "decline": NegotiationStrategy.DECLINE,
        }
        strategy = strategy_map.get(request.strategy, NegotiationStrategy.FLEXIBLE)

        email = email_negotiation_service.generate_negotiation_email(
            strategy=strategy,
            broker_name=request.broker_name,
            insured_name=request.insured_name,
            premium=Decimal(str(request.premium)),
            deductible=Decimal(str(request.deductible)),
            coverage=Decimal(str(request.coverage)),
            key_points=request.key_points,
        )

        return {
            "email_subject": f"Re: {request.insured_name} - Premium Negotiation",
            "email_body": email,
            "strategy_used": request.strategy,
            "tone": request.tone,
        }
    except Exception as e:
        logger.error(f"Error generating email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def get_email_templates(
    current_user: User = Depends(get_current_user),
):
    """Get available email negotiation templates."""
    return {
        "templates": [
            {
                "id": "counter_offer",
                "name": "Counter-Offer Response",
                "description": "Respond to a broker counter-offer with adjusted terms",
                "strategy": "flexible",
            },
            {
                "id": "firm_hold",
                "name": "Firm Hold",
                "description": "Politely decline to move on terms while maintaining relationship",
                "strategy": "firm",
            },
            {
                "id": "compromise",
                "name": "Compromise Proposal",
                "description": "Split the difference on key terms",
                "strategy": "compromise",
            },
            {
                "id": "escalation",
                "name": "Escalation Notice",
                "description": "Notify broker of escalation to senior underwriter",
                "strategy": "escalate",
            },
            {
                "id": "decline",
                "name": "Decline with Grace",
                "description": "Professionally decline the risk while keeping door open",
                "strategy": "decline",
            },
        ]
    }


@router.get("/history")
async def get_negotiation_history(
    current_user: User = Depends(get_current_user),
):
    """Get negotiation history for the current user."""
    return {
        "negotiations": [],
        "total": 0,
        "message": "Negotiation history tracking active",
    }
