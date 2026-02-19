"""
InstantRisk V2 - Predictive Underwriting Router

Endpoints for proactive risk sourcing and opportunity identification.

Routes:
    POST /api/v1/predictive-underwriting/find-risks    - Find ideal risks from market signals
    GET  /api/v1/predictive-underwriting/trends         - Get market trend analysis
    GET  /api/v1/predictive-underwriting/profile        - Get ideal risk profile
    PUT  /api/v1/predictive-underwriting/profile        - Update risk appetite profile
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User
from app.services.predictive_underwriting import predictive_service

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================


class MarketSignal(BaseModel):
    company_name: str = Field("", description="Company name")
    industry: str = Field(..., description="Industry sector")
    revenue: float = Field(0, description="Annual revenue")
    risk_quality: str = Field("medium", description="Risk quality: low, medium, high")
    location: str = Field("", description="Primary location")
    insurance_line: str = Field("cyber", description="Relevant insurance line")
    source: str = Field("", description="Signal source")


class FindRisksRequest(BaseModel):
    market_signals: List[MarketSignal] = Field(
        ..., description="Market signals to analyze"
    )
    insurance_line: str = Field("cyber", description="Target line of business")
    min_fit_score: float = Field(
        0.7, ge=0, le=1, description="Minimum fit score threshold"
    )


class RiskProfileUpdate(BaseModel):
    industries: List[str] = Field(default_factory=list, description="Target industries")
    revenue_range_min: float = Field(1000000, description="Min target revenue")
    revenue_range_max: float = Field(50000000, description="Max target revenue")
    risk_tolerance: str = Field(
        "medium", description="Risk tolerance: low, medium, high"
    )
    preferred_coverage: List[str] = Field(
        default_factory=list, description="Preferred lines of business"
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/find-risks")
async def find_ideal_risks(
    request: FindRisksRequest,
    current_user: User = Depends(get_current_user),
):
    """Analyze market signals to find ideal risk opportunities."""
    try:
        signals = [s.model_dump() for s in request.market_signals]
        result = predictive_service.find_ideal_risks(signals)
        result["insurance_line"] = request.insurance_line
        result["min_fit_score"] = request.min_fit_score
        return result
    except Exception as e:
        logger.error(f"Predictive underwriting error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends")
async def get_market_trends(
    insurance_line: str = "cyber",
    current_user: User = Depends(get_current_user),
):
    """Get current market trends and opportunity indicators."""
    return {
        "insurance_line": insurance_line,
        "trends": [
            {
                "indicator": "Ransomware frequency",
                "direction": "increasing",
                "impact": "high",
                "description": "Ransomware attacks up 37% YoY - driving demand for cyber coverage",
            },
            {
                "indicator": "Regulatory pressure",
                "direction": "increasing",
                "impact": "medium",
                "description": "DORA and NIS2 compliance driving EU cyber insurance demand",
            },
            {
                "indicator": "Market capacity",
                "direction": "stable",
                "impact": "medium",
                "description": "Cyber reinsurance capacity stabilizing after 2024 corrections",
            },
            {
                "indicator": "Premium rates",
                "direction": "softening",
                "impact": "high",
                "description": "Cyber rates declining 5-10% in competitive segments",
            },
            {
                "indicator": "SME adoption",
                "direction": "increasing",
                "impact": "high",
                "description": "SME cyber insurance penetration growing 20% annually",
            },
        ],
        "opportunities": {
            "high_growth": [
                "Healthcare cyber",
                "Manufacturing OT",
                "Financial services",
            ],
            "underserved": ["Agricultural tech", "Renewable energy", "Space tech"],
            "emerging": [
                "AI liability",
                "Quantum computing risk",
                "Digital asset custody",
            ],
        },
    }


@router.get("/profile")
async def get_risk_profile(
    current_user: User = Depends(get_current_user),
):
    """Get the current ideal risk appetite profile."""
    return {
        "profile": predictive_service.ideal_risk_profile,
        "last_updated": "2026-02-01T00:00:00Z",
        "match_count_30d": 42,
        "conversion_rate": 0.23,
    }


@router.put("/profile")
async def update_risk_profile(
    request: RiskProfileUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update the ideal risk appetite profile."""
    try:
        predictive_service.ideal_risk_profile.update(
            {
                "industries": request.industries,
                "revenue_range_min": request.revenue_range_min,
                "revenue_range_max": request.revenue_range_max,
                "risk_tolerance": request.risk_tolerance,
                "preferred_coverage": request.preferred_coverage,
            }
        )
        return {
            "status": "updated",
            "profile": predictive_service.ideal_risk_profile,
        }
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
