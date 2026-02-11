"""
InstantRisk V2 - AI Service

This module provides AI-powered risk analysis using AWS Bedrock Claude
for insurance underwriting decisions.
"""

import asyncio
import json
import os
from typing import Dict, Any, List
import logging
from dotenv import load_dotenv

from app.config import settings
from app.services.bedrock_client import BedrockClient

load_dotenv()

logger = logging.getLogger(__name__)

# System prompt for insurance risk analysis
ANALYSIS_SYSTEM_PROMPT = """You are an expert Lloyd's of London insurance underwriter and risk analyst.

Analyze the provided risk assessment data and return a JSON response with:
1. risk_score (0-100, where 100 is highest risk)
2. confidence_score (0-100, your confidence in the analysis)
3. risk_factors (list of identified risks with severity: high/medium/low)
4. recommendations (list of actionable recommendations)
5. decision (GO if confidence >= 60%, NO-GO if confidence < 60%)
6. summary (2-3 sentence summary)

Consider:
- Premium adequacy vs sum insured
- Territory risk profile
- Industry/category risk factors
- Exposure concentration
- Market conditions
- Regulatory requirements

Respond ONLY with valid JSON, no markdown or explanation."""


class AIService:
    """
    AI-powered risk analysis service using AWS Bedrock Claude.

    Provides comprehensive insurance risk assessment with:
    - Risk scoring
    - Factor identification
    - Recommendations
    - GO/NO-GO decisions
    """

    def __init__(self):
        """Initialize the AI service with Bedrock configuration."""
        self._bedrock = BedrockClient()
        self._initialized = True

    async def analyze_risk(self, assessment) -> Dict[str, Any]:
        """
        Perform comprehensive AI risk analysis using Bedrock Claude.

        Args:
            assessment: The Assessment model instance to analyze.

        Returns:
            dict: Analysis results including risk_score, recommendations, etc.
        """
        # Prepare assessment data
        assessment_data = self._prepare_assessment_data(assessment)

        # Try AI analysis first
        if self._initialized:
            try:
                ai_result = await self._run_ai_analysis(assessment_data)
                if ai_result:
                    return ai_result
            except Exception as e:
                import traceback
                logger.error(f"AI analysis failed, falling back to rules: {e}\n{traceback.format_exc()}")

        # Fallback to rule-based analysis
        return self._run_rule_based_analysis(assessment_data)

    def _prepare_assessment_data(self, assessment) -> Dict[str, Any]:
        """Prepare assessment data for AI analysis."""
        return {
            "reference_number": assessment.reference_number,
            "title": assessment.title,
            "description": assessment.description,
            "risk_category": assessment.risk_category.value if assessment.risk_category else None,
            "insured_name": assessment.insured_name,
            "premium": float(assessment.premium) if assessment.premium else None,
            "sum_insured": float(assessment.sum_insured) if assessment.sum_insured else None,
            "deductible": float(assessment.deductible) if assessment.deductible else None,
            "territory": assessment.territory,
            "exposure_details": assessment.exposure_details,
            "inception_date": assessment.inception_date.isoformat() if assessment.inception_date else None,
            "expiry_date": assessment.expiry_date.isoformat() if assessment.expiry_date else None,
            "ocr_extracted_text": (assessment.ocr_extracted_text or "")[:2000],  # Limit context
        }

    async def _run_ai_analysis(self, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute AI-powered risk analysis using AWS Bedrock Claude."""

        # Build the analysis prompt
        user_prompt = f"""Analyze this insurance risk:

{json.dumps(assessment_data, indent=2, default=str)}

Return JSON with: risk_score, confidence_score, risk_factors, recommendations, decision, summary"""

        messages = [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            content = await self._bedrock.chat(
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
            )

            if not content:
                logger.error("Bedrock returned empty response")
                return None

            # Parse JSON response
            try:
                # Try to extract JSON from response
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                result = json.loads(content)

                # Validate and structure the response
                return {
                    "risk_score": result.get("risk_score", 50),
                    "confidence_score": result.get("confidence_score", 85),
                    "analysis": {
                        "summary": result.get("summary", "AI analysis completed."),
                        "risk_factors": result.get("risk_factors", []),
                        "pricing_analysis": self._analyze_pricing(assessment_data),
                        "exposure_analysis": self._analyze_exposure(assessment_data),
                        "territory_analysis": self._analyze_territory(assessment_data),
                    },
                    "recommendations": result.get("recommendations", []),
                    "suggested_decision": "GO" if result.get("confidence_score", 50) >= 60 else "NO-GO",
                    "ai_powered": True,
                }

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response: {e}")
                return None

        except Exception as e:
            logger.error(f"Bedrock API call failed: {e}")
            return None

    def _run_rule_based_analysis(self, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback rule-based risk analysis."""
        risk_factors = self._identify_risk_factors(assessment_data)
        risk_score = self._calculate_risk_score(risk_factors, assessment_data)
        recommendations = self._generate_recommendations(risk_factors, assessment_data)

        return {
            "risk_score": risk_score,
            "confidence_score": 65,  # Lower confidence for rule-based
            "analysis": {
                "summary": self._generate_summary(assessment_data, risk_score),
                "risk_factors": risk_factors,
                "pricing_analysis": self._analyze_pricing(assessment_data),
                "exposure_analysis": self._analyze_exposure(assessment_data),
                "territory_analysis": self._analyze_territory(assessment_data),
            },
            "recommendations": recommendations,
            "suggested_decision": self._suggest_decision(risk_score),
            "ai_powered": False,
        }

    def _identify_risk_factors(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify risk factors from assessment data."""
        risk_factors = []

        # Check sum insured vs premium ratio
        if data.get("premium") and data.get("sum_insured"):
            rate = (data["premium"] / data["sum_insured"]) * 100
            if rate < 0.1:
                risk_factors.append({
                    "factor": "Low Premium Rate",
                    "severity": "high",
                    "description": f"Premium rate of {rate:.3f}% may be inadequate",
                    "impact_score": 25
                })
            elif rate < 0.2:
                risk_factors.append({
                    "factor": "Below Market Rate",
                    "severity": "medium",
                    "description": f"Premium rate of {rate:.3f}% is below market average",
                    "impact_score": 15
                })

        # Check territory
        high_risk_territories = ["US", "USA", "United States", "China", "Brazil", "Russia"]
        if data.get("territory") and any(t in str(data["territory"]) for t in high_risk_territories):
            risk_factors.append({
                "factor": "High Risk Territory",
                "severity": "medium",
                "description": f"Territory '{data['territory']}' has elevated risk profile",
                "impact_score": 15
            })

        # Check risk category
        high_risk_categories = ["cyber", "aviation", "energy", "professional"]
        if data.get("risk_category") and data["risk_category"].lower() in high_risk_categories:
            risk_factors.append({
                "factor": "High Risk Category",
                "severity": "medium",
                "description": f"Category '{data['risk_category']}' requires enhanced scrutiny",
                "impact_score": 15
            })

        # Check deductible adequacy
        if data.get("deductible") and data.get("sum_insured"):
            deductible_ratio = data["deductible"] / data["sum_insured"]
            if deductible_ratio < 0.005:
                risk_factors.append({
                    "factor": "Low Deductible",
                    "severity": "medium",
                    "description": "Deductible may be too low for risk profile",
                    "impact_score": 10
                })

        # Large exposure
        if data.get("sum_insured") and data["sum_insured"] > 100_000_000:
            risk_factors.append({
                "factor": "Large Exposure",
                "severity": "medium",
                "description": f"Sum insured of {data['sum_insured']:,.0f} requires senior review",
                "impact_score": 10
            })

        return risk_factors

    def _calculate_risk_score(self, risk_factors: List[Dict], data: Dict) -> int:
        """Calculate overall risk score based on identified factors."""
        base_score = 30

        for factor in risk_factors:
            base_score += factor.get("impact_score", 0)

        if data.get("sum_insured"):
            if data["sum_insured"] > 100_000_000:
                base_score += 10
            elif data["sum_insured"] > 50_000_000:
                base_score += 5

        return min(max(base_score, 0), 100)

    def _generate_recommendations(self, risk_factors: List[Dict], data: Dict) -> List[str]:
        """Generate recommendations based on risk analysis."""
        recommendations = []

        for factor in risk_factors:
            if factor["severity"] == "high":
                recommendations.append(f"CRITICAL: Address {factor['factor']} - {factor['description']}")
            elif factor["severity"] == "medium":
                recommendations.append(f"Review {factor['factor']}: Consider additional terms or exclusions")

        if data.get("sum_insured") and data["sum_insured"] > 50_000_000:
            recommendations.append("Consider requiring engineering survey or loss control report")

        if not data.get("description"):
            recommendations.append("Request detailed risk description from broker")

        if not recommendations:
            recommendations.append("Standard underwriting terms may apply")

        return recommendations

    def _generate_summary(self, data: Dict, risk_score: int) -> str:
        """Generate an analysis summary."""
        risk_level = "low" if risk_score < 40 else "moderate" if risk_score < 70 else "high"

        return (
            f"Risk assessment for {data.get('insured_name', 'unnamed insured')} "
            f"indicates {risk_level} overall risk (score: {risk_score}/100). "
            f"Category: {data.get('risk_category', 'unspecified')}. "
            f"Territory: {data.get('territory', 'unspecified')}."
        )

    def _analyze_pricing(self, data: Dict) -> Dict[str, Any]:
        """Analyze pricing adequacy."""
        if not data.get("premium") or not data.get("sum_insured"):
            return {"status": "insufficient_data"}

        rate = (data["premium"] / data["sum_insured"]) * 100
        adequacy = "adequate" if rate >= 0.3 else "review_required" if rate >= 0.15 else "inadequate"

        return {
            "rate_on_line": round(rate, 4),
            "adequacy": adequacy,
            "premium": data["premium"],
            "sum_insured": data["sum_insured"],
            "recommendation": "Consider rate increase" if adequacy != "adequate" else "Rate appears adequate"
        }

    def _analyze_exposure(self, data: Dict) -> Dict[str, Any]:
        """Analyze exposure details."""
        exposure = data.get("exposure_details", {}) or {}

        return {
            "sum_insured": data.get("sum_insured"),
            "deductible": data.get("deductible"),
            "deductible_ratio": round(data["deductible"] / data["sum_insured"] * 100, 2) if data.get("deductible") and data.get("sum_insured") else None,
            "concentration": "high" if (data.get("sum_insured") or 0) > 50_000_000 else "normal",
            "details": exposure
        }

    def _analyze_territory(self, data: Dict) -> Dict[str, Any]:
        """Analyze territory risk."""
        territory = data.get("territory", "Unknown")

        high_risk = ["US", "USA", "United States", "China", "Brazil", "Russia"]
        medium_risk = ["India", "Mexico", "Middle East", "South America"]

        risk_level = "high" if any(t in str(territory) for t in high_risk) else \
                     "medium" if any(t in str(territory) for t in medium_risk) else "standard"

        return {
            "territory": territory,
            "risk_level": risk_level,
            "considerations": self._get_territory_considerations(territory, risk_level)
        }

    def _get_territory_considerations(self, territory: str, risk_level: str) -> List[str]:
        """Get territory-specific considerations."""
        if risk_level == "high":
            return [
                "Consider war and terrorism exclusions",
                "Review sanctions compliance",
                "Check for specific territorial exclusions"
            ]
        elif risk_level == "medium":
            return [
                "Standard territorial limitations apply",
                "Review local regulatory requirements"
            ]
        return ["Standard terms apply"]

    def _suggest_decision(self, risk_score: int) -> str:
        """Suggest underwriting decision based on risk score.
        GO if risk_score < 40 (implies >= 60% confidence), else NO-GO."""
        if risk_score < 40:
            return "GO"
        else:
            return "NO-GO"


# Singleton instance
ai_service = AIService()
