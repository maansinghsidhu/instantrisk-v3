"""
RapidRate API Router - Actuarial pricing endpoints.

Provides:
- POST /price - Invoke Lambda for premium calculation
- POST /simulate - Monte Carlo simulation only
- GET /base-rates - Return base rate table
"""

import json
import logging
from typing import Optional, Dict, Any

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rapidrate", tags=["RapidRate"])


class PriceRequest(BaseModel):
    policy_type: str = Field(..., description="GL, WC, AL, PR")
    state: str = Field(..., description="Two-letter state code")
    exposure: float = Field(..., description="Exposure base amount")
    deductible: float = Field(0, description="Per-claim deductible")
    limit: Optional[float] = Field(None, description="Per-claim limit")
    industry_code: Optional[str] = Field(None, description="NAICS code")
    insured_loss_history: Optional[Dict[str, Any]] = None


class SimulateRequest(BaseModel):
    policy_type: str
    state: str
    exposure: float
    n_simulations: int = Field(10000, ge=1000, le=100000)


# Base rates table (publicly visible for UI)
BASE_RATES = {
    "GL": {
        "name": "General Liability",
        "base_rate_per_1000": 2.50,
        "min_premium": 500,
        "rate_range": {"low": 1.00, "high": 8.00},
    },
    "WC": {
        "name": "Workers Compensation",
        "base_rate_per_100_payroll": 1.20,
        "min_premium": 750,
        "rate_range": {"low": 0.50, "high": 15.00},
    },
    "AL": {
        "name": "Auto Liability",
        "base_rate_per_vehicle": 1200,
        "min_premium": 1000,
        "rate_range": {"low": 800, "high": 5000},
    },
    "PR": {
        "name": "Property",
        "base_rate_per_1000_tiv": 0.80,
        "min_premium": 500,
        "rate_range": {"low": 0.25, "high": 5.00},
    },
}


def _invoke_lambda(payload: Dict) -> Dict:
    """Invoke RapidRate Lambda and return response."""
    try:
        lambda_client = boto3.client(
            "lambda",
            region_name=getattr(settings, "RAPIDRATE_LAMBDA_REGION", "us-east-1"),
        )
        response = lambda_client.invoke(
            FunctionName=getattr(settings, "RAPIDRATE_LAMBDA_NAME", "instantrisk-rapidrate"),
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        result = json.loads(response["Payload"].read())

        if response.get("StatusCode") == 200:
            body = json.loads(result.get("body", "{}")) if isinstance(result.get("body"), str) else result.get("body", result)
            return body
        else:
            return {"success": False, "error": "Lambda invocation failed"}

    except ClientError as e:
        logger.error(f"Lambda client error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"RapidRate Lambda error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/price")
async def get_price(
    request: PriceRequest,
    current_user=Depends(get_current_user),
):
    """Get actuarial pricing from RapidRate Lambda."""
    payload = {
        "action": "price",
        "policy_type": request.policy_type,
        "state": request.state,
        "exposure": request.exposure,
        "deductible": request.deductible,
        "limit": request.limit or 1000000,
        "industry_code": request.industry_code,
        "features": {
            "exposure": request.exposure,
            "deductible": request.deductible,
            "limit": request.limit or 1000000,
            "state_code": request.state,
        },
    }

    if request.insured_loss_history:
        payload["insured_loss_history"] = request.insured_loss_history

    result = _invoke_lambda(payload)

    if result.get("success") is False:
        # Return a structured fallback response
        return {
            "success": False,
            "error": result.get("error", "Pricing service unavailable"),
            "fallback": _calculate_fallback_premium(request),
        }

    return {"success": True, "data": result.get("data", result)}


@router.post("/simulate")
async def run_simulation(
    request: SimulateRequest,
    current_user=Depends(get_current_user),
):
    """Run Monte Carlo simulation for loss distribution."""
    payload = {
        "action": "simulate",
        "policy_type": request.policy_type,
        "state": request.state,
        "exposure": request.exposure,
        "n_simulations": request.n_simulations,
    }

    result = _invoke_lambda(payload)

    if result.get("success") is False:
        return {"success": False, "error": result.get("error", "Simulation unavailable")}

    return {"success": True, "data": result.get("data", result)}


@router.get("/base-rates")
async def get_base_rates(
    current_user=Depends(get_current_user),
):
    """Return base rate table for all policy types."""
    return {"success": True, "data": BASE_RATES}


def _calculate_fallback_premium(request: PriceRequest) -> Dict:
    """Calculate a simple fallback premium when Lambda is unavailable."""
    rates = BASE_RATES.get(request.policy_type, BASE_RATES["GL"])

    if request.policy_type == "WC":
        base = request.exposure * rates["base_rate_per_100_payroll"] / 100
    elif request.policy_type == "AL":
        base = request.exposure * rates["base_rate_per_vehicle"] / 1000
    elif request.policy_type == "PR":
        base = request.exposure * rates["base_rate_per_1000_tiv"] / 1000
    else:
        base = request.exposure * rates["base_rate_per_1000"] / 1000

    premium = max(base, rates["min_premium"])

    return {
        "estimated_premium": round(premium, 2),
        "premium_range": {
            "low": round(premium * 0.7, 2),
            "high": round(premium * 1.4, 2),
        },
        "source": "fallback_calculation",
        "note": "Estimate only - ML model unavailable",
    }
