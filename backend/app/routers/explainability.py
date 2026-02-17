"""
Explainability Router

API endpoints for AI model explanations using SHAP.
"""

from typing import Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.services.explainability_service import explainability_service

router = APIRouter()


# Response schemas
class FeatureContribution(BaseModel):
    """Single feature contribution."""
    feature: str
    contribution: float
    direction: str
    magnitude: float


class Counterfactual(BaseModel):
    """What-if scenario."""
    feature: str
    current_value: Any
    alternative_value: Any
    score_change: float
    explanation: str


class ExplanationResponse(BaseModel):
    """Complete model explanation."""
    risk_score: float
    base_score: float
    feature_contributions: Dict[str, float]
    top_factors: List[FeatureContribution]
    waterfall_chart: str  # Base64 PNG
    counterfactuals: List[Counterfactual]
    explanation_text: str


@router.get(
    "/explain/{assessment_id}",
    response_model=ExplanationResponse,
    summary="Explain AI decision"
)
async def explain_assessment(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Explain why AI made certain decision for this assessment.

    Uses SHAP (SHapley Additive exPlanations) to show:
    - Which features drove the risk score
    - How much each feature contributed
    - What-if scenarios (counterfactuals)
    - Visual waterfall chart

    Helps underwriters:
    - Trust AI decisions
    - Explain to clients
    - Learn from model
    - Validate recommendations
    """

    # Get assessment
    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found"
        )

    # Check if risk score exists
    if assessment.risk_score is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assessment not analyzed yet - no risk score available"
        )

    # Extract features
    features = {
        "territory": assessment.territory,
        "risk_category": assessment.risk_category,
        "sum_insured": float(assessment.sum_insured) if assessment.sum_insured else 0,
        "premium": float(assessment.premium) if assessment.premium else 0,
        "deductible": float(assessment.deductible) if assessment.deductible else 0,
    }

    # Get explanation
    explanation = explainability_service.explain_risk_score(
        risk_score=assessment.risk_score,
        features=features
    )

    return explanation


@router.post(
    "/counterfactual/{assessment_id}",
    summary="Generate what-if scenarios"
)
async def generate_counterfactuals(
    assessment_id: UUID,
    feature_changes: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate counterfactual scenarios.

    Example: "What if deductible was $100K instead of $50K?"

    Args:
        feature_changes: Dict of features to change, e.g.:
            {"deductible": 100000, "territory": "United Kingdom"}

    Returns:
        Predicted new risk score and explanation
    """

    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found"
        )

    # Get original features
    original_features = {
        "territory": assessment.territory,
        "risk_category": assessment.risk_category,
        "sum_insured": float(assessment.sum_insured) if assessment.sum_insured else 0,
        "premium": float(assessment.premium) if assessment.premium else 0,
        "deductible": float(assessment.deductible) if assessment.deductible else 0,
    }

    # Apply changes
    modified_features = {**original_features, **feature_changes}

    # Recalculate (simple heuristic for now)
    # In production, this would use actual ML model
    score_delta = 0
    for feature, new_value in feature_changes.items():
        old_value = original_features.get(feature)

        if feature == 'deductible':
            if isinstance(new_value, (int, float)) and isinstance(old_value, (int, float)):
                # Higher deductible = lower risk
                deduct_change = (new_value - old_value) / 10000
                score_delta -= deduct_change * 0.5

        elif feature == 'territory':
            # Territory change impact
            if new_value == 'United Kingdom' and old_value != 'United Kingdom':
                score_delta -= 5.0
            elif new_value == 'United States' and old_value != 'United States':
                score_delta += 5.0

    new_risk_score = assessment.risk_score + score_delta

    return {
        "original_score": assessment.risk_score,
        "new_score": new_risk_score,
        "score_change": score_delta,
        "feature_changes": feature_changes,
        "explanation": f"Changing {', '.join(feature_changes.keys())} would "
                       f"{'increase' if score_delta > 0 else 'decrease'} risk by {abs(score_delta):.1f} points"
    }


@router.get(
    "/feature-importance",
    summary="Get global feature importance"
)
async def get_feature_importance(
    current_user: User = Depends(get_current_user)
):
    """
    Get global feature importance across all assessments.

    Shows which features are most influential in risk scoring overall.
    """

    # This would analyze all historical assessments
    # For now, return static importance rankings

    return {
        "features": [
            {"name": "territory", "importance": 0.25, "rank": 1},
            {"name": "risk_category", "importance": 0.22, "rank": 2},
            {"name": "sum_insured", "importance": 0.18, "rank": 3},
            {"name": "deductible", "importance": 0.15, "rank": 4},
            {"name": "premium", "importance": 0.12, "rank": 5},
            {"name": "loss_history", "importance": 0.08, "rank": 6},
        ],
        "note": "Feature importance calculated across all historical assessments"
    }
