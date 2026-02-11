"""
InstantRisk V3 - D&O (Directors & Officers) Underwriting Agent

Specialized AI agent for D&O liability assessment.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List


@dataclass
class GovernanceScore:
    """Corporate governance assessment."""
    overall_score: float
    board_independence: float
    audit_quality: float
    compensation_alignment: float
    risk_oversight: float
    concerns: List[str]


@dataclass
class SecuritiesRisk:
    """Securities litigation risk assessment."""
    risk_score: float
    stock_volatility: str
    earnings_quality: str
    disclosure_risk: str
    class_action_exposure: bool


@dataclass
class RetentionStructure:
    """Recommended D&O retention structure."""
    side_a_retention: Decimal
    side_b_retention: Decimal
    side_c_retention: Decimal
    rationale: str


class DOUnderwritingAgent:
    """AI agent for Directors & Officers liability underwriting."""

    # Industry D&O risk factors
    INDUSTRY_RISK = {
        'financial_services': 0.35,
        'technology': 0.30,
        'healthcare': 0.28,
        'energy': 0.25,
        'retail': 0.20,
        'manufacturing': 0.18,
        'professional_services': 0.15,
    }

    async def analyze_governance(self, company: Dict[str, Any]) -> GovernanceScore:
        """Analyze corporate governance quality."""
        board_size = company.get('board_size', 5)
        independent_directors = company.get('independent_directors', 0)
        audit_committee = company.get('audit_committee_independent', False)
        ceo_chair_separate = company.get('ceo_chair_separate', False)
        clawback_policy = company.get('clawback_policy', False)

        concerns = []

        # Board independence score
        independence_ratio = independent_directors / board_size if board_size > 0 else 0
        board_score = min(100, independence_ratio * 100)
        if independence_ratio < 0.5:
            concerns.append("Majority of board is not independent")

        # Audit quality
        audit_score = 70
        if audit_committee:
            audit_score += 20
        if company.get('big4_auditor', False):
            audit_score += 10
        else:
            concerns.append("Not using Big 4 auditor")

        # Compensation alignment
        comp_score = 50
        if clawback_policy:
            comp_score += 25
        if company.get('say_on_pay_support', 0) > 70:
            comp_score += 25
        else:
            concerns.append("Low say-on-pay support")

        # Risk oversight
        risk_score = 50
        if company.get('risk_committee', False):
            risk_score += 25
        if company.get('cro_appointed', False):
            risk_score += 25
        if ceo_chair_separate:
            risk_score += 10
        else:
            concerns.append("CEO also serves as Chair")

        overall = (board_score + audit_score + comp_score + risk_score) / 4

        return GovernanceScore(
            overall_score=overall,
            board_independence=board_score,
            audit_quality=audit_score,
            compensation_alignment=comp_score,
            risk_oversight=risk_score,
            concerns=concerns,
        )

    async def assess_securities_exposure(self, financials: Dict[str, Any]) -> SecuritiesRisk:
        """Assess securities litigation risk."""
        market_cap = Decimal(str(financials.get('market_cap', 0)))
        revenue_growth = financials.get('revenue_growth', 0)
        earnings_volatility = financials.get('earnings_volatility', 0)
        stock_volatility = financials.get('stock_volatility', 0)
        is_public = financials.get('is_public', False)

        base_score = 30

        # Public company exposure
        if is_public:
            base_score += 20
            if market_cap > Decimal('10000000000'):  # >$10B
                base_score += 15
            elif market_cap > Decimal('1000000000'):  # >$1B
                base_score += 10

        # Volatility factors
        if stock_volatility > 40:
            base_score += 15
            vol_rating = 'high'
        elif stock_volatility > 20:
            base_score += 8
            vol_rating = 'moderate'
        else:
            vol_rating = 'low'

        # Earnings quality
        if earnings_volatility > 30:
            base_score += 10
            earnings_quality = 'volatile'
        elif earnings_volatility > 15:
            base_score += 5
            earnings_quality = 'moderate'
        else:
            earnings_quality = 'stable'

        # Disclosure risk
        if financials.get('restatements', 0) > 0:
            base_score += 20
            disclosure_risk = 'elevated'
        elif financials.get('material_weaknesses', False):
            base_score += 15
            disclosure_risk = 'moderate'
        else:
            disclosure_risk = 'low'

        return SecuritiesRisk(
            risk_score=min(100, base_score),
            stock_volatility=vol_rating,
            earnings_quality=earnings_quality,
            disclosure_risk=disclosure_risk,
            class_action_exposure=is_public and market_cap > Decimal('500000000'),
        )

    async def recommend_retentions(self, company_size: str) -> RetentionStructure:
        """Recommend D&O retention structure by company size."""
        structures = {
            'small': {  # <$100M revenue
                'a': Decimal('0'),  # Side A: No retention (personal asset protection)
                'b': Decimal('50000'),
                'c': Decimal('100000'),
                'rationale': 'Lower retentions for smaller company with limited resources',
            },
            'medium': {  # $100M-$1B revenue
                'a': Decimal('0'),
                'b': Decimal('250000'),
                'c': Decimal('500000'),
                'rationale': 'Standard retention structure for mid-market company',
            },
            'large': {  # $1B+ revenue
                'a': Decimal('0'),
                'b': Decimal('1000000'),
                'c': Decimal('2500000'),
                'rationale': 'Higher retentions reflecting financial capacity',
            },
            'public': {
                'a': Decimal('0'),
                'b': Decimal('2500000'),
                'c': Decimal('5000000'),
                'rationale': 'Elevated retentions for public company securities exposure',
            },
        }

        size_key = company_size.lower() if company_size.lower() in structures else 'medium'
        struct = structures[size_key]

        return RetentionStructure(
            side_a_retention=struct['a'],
            side_b_retention=struct['b'],
            side_c_retention=struct['c'],
            rationale=struct['rationale'],
        )

    async def calculate_premium(
        self,
        limit: Decimal,
        governance: GovernanceScore,
        securities: SecuritiesRisk,
        industry: str,
    ) -> Dict[str, Any]:
        """Calculate D&O premium indication."""
        # Base rate
        industry_factor = self.INDUSTRY_RISK.get(industry.lower(), 0.20)
        base_rate = Decimal(str(industry_factor))

        # Governance adjustment (-20% to +20%)
        gov_adjustment = Decimal(str((100 - governance.overall_score) / 500))

        # Securities risk adjustment
        sec_adjustment = Decimal(str(securities.risk_score / 400))

        total_rate = base_rate + gov_adjustment + sec_adjustment
        premium = limit * total_rate

        return {
            'limit': float(limit),
            'base_rate': float(base_rate),
            'governance_adjustment': float(gov_adjustment),
            'securities_adjustment': float(sec_adjustment),
            'total_rate': float(total_rate),
            'premium_indication': float(max(premium, Decimal('25000'))),
            'minimum_premium': 25000,
        }
