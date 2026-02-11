"""
InstantRisk V3 - Political Risk Underwriting Agent

Specialized AI agent for political risk and trade credit assessment.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List


@dataclass
class CountryRisk:
    """Country risk assessment."""
    country_code: str
    risk_score: float
    risk_tier: str  # 1-7
    sanctions_status: str
    political_stability: str
    economic_outlook: str
    key_risks: List[str]


@dataclass
class CreditRisk:
    """Counterparty credit risk assessment."""
    entity_name: str
    credit_score: float
    recommended_limit: Decimal
    payment_terms: str
    risk_factors: List[str]


class PoliticalRiskAgent:
    """AI agent for political risk and trade credit underwriting."""

    # Country risk tiers (simplified)
    COUNTRY_TIERS = {
        # Tier 1 - Low risk
        'US': 1, 'GB': 1, 'DE': 1, 'FR': 1, 'JP': 1, 'AU': 1, 'CA': 1,
        # Tier 2-3 - Moderate
        'BR': 3, 'MX': 3, 'IN': 3, 'CN': 3, 'ZA': 3,
        # Tier 4-5 - Elevated
        'TR': 4, 'EG': 4, 'NG': 5, 'PK': 5,
        # Tier 6-7 - High
        'VE': 7, 'IR': 7, 'SY': 7, 'RU': 6, 'BY': 6,
    }

    # Sanctioned countries (simplified list)
    SANCTIONED = ['IR', 'KP', 'SY', 'CU', 'RU', 'BY']

    async def assess_country_risk(self, country: str) -> CountryRisk:
        """Assess political risk for a country."""
        country_upper = country.upper()[:2]
        tier = self.COUNTRY_TIERS.get(country_upper, 5)
        is_sanctioned = country_upper in self.SANCTIONED

        # Calculate risk score from tier
        risk_score = tier * 14.3  # Scales to ~100

        # Determine risk factors
        key_risks = []
        if tier >= 5:
            key_risks.append("Political instability")
        if tier >= 4:
            key_risks.append("Currency volatility")
        if tier >= 3:
            key_risks.append("Contract frustration risk")
        if is_sanctioned:
            key_risks.append("Sanctions compliance required")

        return CountryRisk(
            country_code=country_upper,
            risk_score=min(100, risk_score),
            risk_tier=str(tier),
            sanctions_status="sanctioned" if is_sanctioned else "clear",
            political_stability="low" if tier >= 5 else "moderate" if tier >= 3 else "stable",
            economic_outlook="negative" if tier >= 5 else "neutral" if tier >= 3 else "positive",
            key_risks=key_risks,
        )

    async def evaluate_counterparty(self, entity: Dict[str, Any]) -> CreditRisk:
        """Evaluate counterparty credit risk."""
        entity_name = entity.get('name', 'Unknown')
        country = entity.get('country', 'US')
        revenue = Decimal(str(entity.get('revenue', 0)))
        years_in_business = entity.get('years_in_business', 0)
        payment_history = entity.get('payment_history', 'unknown')

        # Base credit score
        base_score = 50

        # Country adjustment
        country_risk = await self.assess_country_risk(country)
        base_score -= country_risk.risk_score * 0.3

        # Business maturity
        if years_in_business > 10:
            base_score += 15
        elif years_in_business > 5:
            base_score += 10
        elif years_in_business > 2:
            base_score += 5

        # Payment history
        if payment_history == 'excellent':
            base_score += 20
        elif payment_history == 'good':
            base_score += 10
        elif payment_history == 'poor':
            base_score -= 20

        credit_score = max(0, min(100, base_score))

        # Calculate recommended limit
        if credit_score >= 70:
            limit_pct = Decimal('0.10')
        elif credit_score >= 50:
            limit_pct = Decimal('0.05')
        else:
            limit_pct = Decimal('0.02')

        recommended_limit = revenue * limit_pct

        # Risk factors
        risk_factors = []
        if credit_score < 50:
            risk_factors.append("Low credit score")
        if years_in_business < 3:
            risk_factors.append("Limited trading history")
        if country_risk.risk_tier in ['5', '6', '7']:
            risk_factors.append(f"High-risk country ({country})")

        return CreditRisk(
            entity_name=entity_name,
            credit_score=credit_score,
            recommended_limit=max(Decimal('10000'), min(Decimal('10000000'), recommended_limit)),
            payment_terms="LC required" if credit_score < 50 else "Net 60" if credit_score < 70 else "Net 90",
            risk_factors=risk_factors,
        )

    async def generate_tenor_pricing(self, tenor_months: int, country: str) -> Dict[str, Any]:
        """Generate pricing by tenor length."""
        country_risk = await self.assess_country_risk(country)

        # Base rate increases with tenor
        base_rate = Decimal('0.005')  # 0.5% base
        tenor_factor = Decimal(str(1 + (tenor_months / 12) * 0.5))
        risk_factor = Decimal(str(1 + country_risk.risk_score / 100))

        rate = base_rate * tenor_factor * risk_factor

        return {
            'tenor_months': tenor_months,
            'country': country,
            'rate_per_annum': float(rate * 12),
            'rate_flat': float(rate * tenor_months / 12),
            'minimum_premium': 2500,
        }
