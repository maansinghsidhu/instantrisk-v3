"""
InstantRisk V2 - Scenario Simulation Router

Endpoints for Monte Carlo risk modeling and what-if analysis.

Routes:
    POST /api/v1/scenarios/monte-carlo       - Run Monte Carlo simulation
    POST /api/v1/scenarios/impact-analysis   - Calculate impact of changes
    GET  /api/v1/scenarios/presets            - Get simulation presets
"""

import logging
from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User
from app.services.scenario_simulation import scenario_service

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================


class MonteCarloRequest(BaseModel):
    premium: float = Field(..., description="Base premium amount")
    loss_ratio: float = Field(0.65, description="Expected loss ratio (0-1)")
    exposure_count: int = Field(100, description="Number of exposures")
    iterations: int = Field(
        10000, ge=100, le=100000, description="Simulation iterations"
    )
    insurance_line: str = Field("cyber", description="Line of business")


class ImpactChange(BaseModel):
    description: str = Field(..., description="Description of the change")
    factor: float = Field(..., description="Multiplicative factor")


class ImpactAnalysisRequest(BaseModel):
    premium: float = Field(..., description="Base premium")
    expected_loss: float = Field(..., description="Expected loss amount")
    changes: List[ImpactChange] = Field(..., description="List of changes to analyze")


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/monte-carlo")
async def run_monte_carlo(
    request: MonteCarloRequest,
    current_user: User = Depends(get_current_user),
):
    """Run Monte Carlo simulation for risk modeling."""
    try:
        result = scenario_service.run_monte_carlo(
            premium=Decimal(str(request.premium)),
            loss_ratio=request.loss_ratio,
            exposure_count=request.exposure_count,
            iterations=request.iterations,
        )
        result["insurance_line"] = request.insurance_line
        result["iterations"] = request.iterations
        return result
    except Exception as e:
        logger.error(f"Monte Carlo simulation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/impact-analysis")
async def run_impact_analysis(
    request: ImpactAnalysisRequest,
    current_user: User = Depends(get_current_user),
):
    """Calculate the impact of proposed changes on a risk scenario."""
    try:
        base = {
            "premium": request.premium,
            "expected_loss": request.expected_loss,
        }
        changes = [
            {"description": c.description, "factor": c.factor} for c in request.changes
        ]
        result = scenario_service.calculate_impact(base, changes)
        return result
    except Exception as e:
        logger.error(f"Impact analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presets")
async def get_simulation_presets(
    current_user: User = Depends(get_current_user),
):
    """Get predefined simulation scenarios by line of business."""
    return {
        "presets": [
            {
                "id": "cyber_standard",
                "name": "Cyber - Standard Risk",
                "insurance_line": "cyber",
                "premium": 125000,
                "loss_ratio": 0.55,
                "exposure_count": 50,
                "description": "Typical mid-market cyber policy scenario",
            },
            {
                "id": "cyber_high_risk",
                "name": "Cyber - High Risk",
                "insurance_line": "cyber",
                "premium": 250000,
                "loss_ratio": 0.75,
                "exposure_count": 100,
                "description": "High-risk tech company with elevated breach probability",
            },
            {
                "id": "property_standard",
                "name": "Property - Standard",
                "insurance_line": "property",
                "premium": 500000,
                "loss_ratio": 0.45,
                "exposure_count": 200,
                "description": "Standard commercial property portfolio",
            },
            {
                "id": "liability_professional",
                "name": "Professional Liability",
                "insurance_line": "liability",
                "premium": 75000,
                "loss_ratio": 0.60,
                "exposure_count": 30,
                "description": "Professional services E&O coverage",
            },
            {
                "id": "cat_nat_cat",
                "name": "Natural Catastrophe",
                "insurance_line": "property",
                "premium": 1000000,
                "loss_ratio": 0.35,
                "exposure_count": 500,
                "description": "Natural catastrophe excess of loss scenario",
            },
        ]
    }
