"""
Predictive Underwriting Service - Proactive risk sourcing.

Identifies ideal risks based on market signals and historical patterns.
"""

from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta


class PredictiveUnderwritingService:
    def __init__(self):
        self.ideal_risk_profile = {
            "industries": ["Technology", "Healthcare", "Professional Services"],
            "revenue_range_min": 1000000,
            "revenue_range_max": 50000000,
            "risk_tolerance": "medium",
            "preferred_coverage": ["cyber", "property", "liability"],
        }

    def find_ideal_risks(self, market_signals: List[Dict]) -> Dict:
        matched_risks = []
        for signal in market_signals:
            score = self._calculate_fit_score(signal)
            if score >= 0.7:
                matched_risks.append(
                    {
                        "signal": signal,
                        "fit_score": score,
                        "recommended_action": "proactive_outreach",
                        "estimated_premium": self._estimate_premium(signal),
                    }
                )

        matched_risks.sort(key=lambda x: x["fit_score"], reverse=True)

        return {
            "total_opportunities": len(matched_risks),
            "high_priority": [r for r in matched_risks if r["fit_score"] >= 0.8],
            "medium_priority": [
                r for r in matched_risks if 0.7 <= r["fit_score"] < 0.8
            ],
            "market_trends": self._analyze_trends(market_signals),
        }

    def _calculate_fit_score(self, signal: Dict) -> float:
        score = 0.0
        if signal.get("industry") in self.ideal_risk_profile["industries"]:
            score += 0.3
        revenue = signal.get("revenue", 0)
        if (
            self.ideal_risk_profile["revenue_range_min"]
            <= revenue
            <= self.ideal_risk_profile["revenue_range_max"]
        ):
            score += 0.3
        if signal.get("risk_quality") == "low":
            score += 0.4
        return min(score, 1.0)

    def _estimate_premium(self, signal: Dict) -> Decimal:
        base_premium = 25000
        industry_factor = 1.2 if signal.get("industry") == "Technology" else 1.0
        return Decimal(str(base_premium * industry_factor))

    def _analyze_trends(self, signals: List[Dict]) -> Dict:
        industries = {}
        for s in signals:
            ind = s.get("industry", "Unknown")
            industries[ind] = industries.get(ind, 0) + 1
        return {
            "top_industries": sorted(
                industries.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "opportunity_count": len(signals),
        }


predictive_service = PredictiveUnderwritingService()
