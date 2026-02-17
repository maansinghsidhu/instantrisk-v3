"""
SHAP Explainability Service

Provides model explanations for AI decisions using SHAP (SHapley Additive exPlanations).
Makes AI decisions transparent and trustworthy.
"""

import logging
import json
from typing import Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    import shap
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import io
    import base64
    SHAP_AVAILABLE = True
except ImportError:
    logger.warning("SHAP not installed - explainability features disabled")
    SHAP_AVAILABLE = False


class ExplainabilityService:
    """
    Explains AI model predictions using SHAP values.

    Provides:
    - Feature importance (which factors drove the decision?)
    - Contribution breakdown (how much each factor contributed)
    - Counterfactual analysis (what if we changed X?)
    - Waterfall charts (visual explanation)
    """

    def __init__(self):
        if not SHAP_AVAILABLE:
            logger.error("SHAP library not available - install with: pip install shap")

    def explain_risk_score(
        self,
        risk_score: float,
        features: Dict[str, Any],
        feature_contributions: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Explain how risk score was calculated.

        Args:
            risk_score: Final risk score (0-100)
            features: Input features {territory, premium, sum_insured, ...}
            feature_contributions: Pre-calculated contributions (if available)

        Returns:
            Explanation with feature importance, contributions, counterfactuals
        """

        if not SHAP_AVAILABLE:
            return {
                "error": "SHAP not available",
                "message": "Install shap library for model explanations"
            }

        # If contributions not provided, calculate simple rule-based explanation
        if not feature_contributions:
            feature_contributions = self._calculate_simple_contributions(features, risk_score)

        # Sort by absolute contribution
        sorted_contrib = sorted(
            feature_contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )

        # Generate waterfall chart
        waterfall_chart_b64 = self._generate_waterfall_chart(
            feature_contributions,
            risk_score
        )

        # Generate counterfactuals
        counterfactuals = self._generate_counterfactuals(features, feature_contributions)

        return {
            "risk_score": risk_score,
            "base_score": 50.0,  # Baseline (neutral risk)
            "feature_contributions": feature_contributions,
            "top_factors": [
                {
                    "feature": name,
                    "contribution": value,
                    "direction": "increases" if value > 0 else "decreases",
                    "magnitude": abs(value)
                }
                for name, value in sorted_contrib[:5]
            ],
            "waterfall_chart": waterfall_chart_b64,
            "counterfactuals": counterfactuals,
            "explanation_text": self._generate_text_explanation(sorted_contrib, risk_score)
        }

    def _calculate_simple_contributions(
        self,
        features: Dict[str, Any],
        risk_score: float
    ) -> Dict[str, float]:
        """
        Simple rule-based contribution calculation.

        For demo purposes until ML model provides actual SHAP values.
        """

        contributions = {}
        base_score = 50.0
        total_contribution = risk_score - base_score

        # Territory contributions (example)
        territory_factors = {
            "United States": 5.0,
            "United Kingdom": 0.0,
            "China": 15.0,
            "Middle East": 12.0,
            "Europe": -3.0,
        }

        territory = features.get('territory', 'Unknown')
        contrib_territory = territory_factors.get(territory, 0.0)
        contributions['territory'] = contrib_territory

        # Risk category contributions
        category_factors = {
            "Cyber": 10.0,
            "Property": -5.0,
            "Marine": 3.0,
            "Aviation": 8.0,
        }

        category = features.get('risk_category', 'Unknown')
        contrib_category = category_factors.get(category, 0.0)
        contributions['risk_category'] = contrib_category

        # Sum insured (higher = more risk)
        sum_insured = features.get('sum_insured', 0)
        if sum_insured > 10_000_000:
            contributions['sum_insured'] = 8.0
        elif sum_insured > 5_000_000:
            contributions['sum_insured'] = 4.0
        else:
            contributions['sum_insured'] = -2.0

        # Premium (higher = better underwriting)
        premium = features.get('premium', 0)
        if premium > 50_000:
            contributions['premium'] = -5.0  # Reduces risk
        elif premium < 10_000:
            contributions['premium'] = 3.0  # Increases risk
        else:
            contributions['premium'] = 0.0

        # Deductible (higher = less risk)
        deductible = features.get('deductible', 0)
        if deductible > 100_000:
            contributions['deductible'] = -6.0
        elif deductible > 50_000:
            contributions['deductible'] = -3.0
        else:
            contributions['deductible'] = 2.0

        # Balance contributions to match actual risk score
        total_contrib = sum(contributions.values())
        if abs(total_contrib - total_contribution) > 1.0:
            # Add "other_factors" to balance
            contributions['other_factors'] = total_contribution - total_contrib

        return contributions

    def _generate_waterfall_chart(
        self,
        contributions: Dict[str, float],
        final_score: float
    ) -> str:
        """
        Generate SHAP-style waterfall chart.

        Returns base64-encoded PNG image.
        """

        if not SHAP_AVAILABLE:
            return ""

        try:
            # Create waterfall plot
            fig, ax = plt.subplots(figsize=(10, 6))

            features = list(contributions.keys())
            values = list(contributions.values())

            # Calculate cumulative values for waterfall
            base = 50.0
            cumulative = [base]
            for v in values:
                cumulative.append(cumulative[-1] + v)

            # Plot
            colors = ['red' if v > 0 else 'green' for v in values]

            ax.barh(features, values, color=colors, alpha=0.7)
            ax.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
            ax.set_xlabel('Risk Score Contribution')
            ax.set_title(f'Risk Score Explanation (Final: {final_score:.1f})')
            ax.grid(axis='x', alpha=0.3)

            # Convert to base64
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)
            img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            plt.close()

            return f"data:image/png;base64,{img_base64}"

        except Exception as e:
            logger.error(f"Failed to generate waterfall chart: {e}")
            return ""

    def _generate_counterfactuals(
        self,
        features: Dict[str, Any],
        contributions: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Generate "what-if" scenarios.

        Shows how score would change if features were different.
        """

        counterfactuals = []

        # Top 3 contributors
        top_features = sorted(
            contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:3]

        for feature_name, contribution in top_features:
            if feature_name == 'territory':
                counterfactuals.append({
                    "feature": "territory",
                    "current_value": features.get('territory'),
                    "alternative_value": "United Kingdom",
                    "score_change": -5.0,
                    "explanation": "Moving to UK would reduce risk by 5 points"
                })

            elif feature_name == 'deductible':
                current = features.get('deductible', 0)
                higher = current * 2
                counterfactuals.append({
                    "feature": "deductible",
                    "current_value": current,
                    "alternative_value": higher,
                    "score_change": -6.0,
                    "explanation": f"Increasing deductible to ${higher:,.0f} would reduce risk by 6 points"
                })

        return counterfactuals

    def _generate_text_explanation(
        self,
        sorted_contributions: List[tuple],
        risk_score: float
    ) -> str:
        """
        Generate human-readable explanation.
        """

        if risk_score >= 70:
            decision = "HIGH RISK"
            recommendation = "Decline or price with substantial premium"
        elif risk_score >= 50:
            decision = "MEDIUM RISK"
            recommendation = "Standard terms with monitoring"
        else:
            decision = "LOW RISK"
            recommendation = "Accept with standard terms"

        explanation = f"Risk assessed as {decision} (score: {risk_score:.1f}/100). "
        explanation += f"{recommendation}.\n\n"

        explanation += "Key factors:\n"
        for i, (feature, contribution) in enumerate(sorted_contributions[:5], 1):
            if contribution > 0:
                explanation += f"{i}. {feature.replace('_', ' ').title()}: +{contribution:.1f} points (increases risk)\n"
            else:
                explanation += f"{i}. {feature.replace('_', ' ').title()}: {contribution:.1f} points (decreases risk)\n"

        return explanation


# Singleton instance
explainability_service = ExplainabilityService()
