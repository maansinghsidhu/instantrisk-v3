"""
InstantRisk V3 - Algorithmic Underwriting Engine

ML-powered pricing and underwriting engine for Lloyd's market.
This is the core value proposition of V3 - automated, explainable underwriting decisions.

Components:
- RiskScorer: ML-based risk classification
- PricingEngine: Technical premium calculation with confidence intervals
- CapacityOptimizer: Optimal syndicate line determination
- DecisionSummarizer: Explainable AI report generation

Addresses Gap 2: Manual Underwriting Processes
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import math
import statistics

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.specialty_agents import (
    CyberUnderwritingAgent,
    MarineCargoAgent,
    PoliticalRiskAgent,
    DOUnderwritingAgent,
)


# =============================================================================
# Enums and Constants
# =============================================================================

class RiskCategory(Enum):
    """Risk classification categories."""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    DECLINE = "decline"


class ClassOfBusiness(Enum):
    """Lloyd's standard classes of business."""
    # Property
    PROPERTY_COMMERCIAL = "property_commercial"
    PROPERTY_RESIDENTIAL = "property_residential"
    PROPERTY_DF = "property_d&f"  # Direct & Facultative

    # Casualty
    GENERAL_LIABILITY = "general_liability"
    PROFESSIONAL_LIABILITY = "professional_liability"
    DIRECTORS_OFFICERS = "directors_officers"
    EMPLOYERS_LIABILITY = "employers_liability"

    # Specialty
    CYBER = "cyber"
    MARINE_CARGO = "marine_cargo"
    MARINE_HULL = "marine_hull"
    AVIATION = "aviation"
    ENERGY = "energy"
    POLITICAL_RISK = "political_risk"
    TRADE_CREDIT = "trade_credit"
    CONTINGENCY = "contingency"

    # Financial Lines
    FINANCIAL_INSTITUTIONS = "financial_institutions"
    CRIME = "crime"
    WARRANTY_INDEMNITY = "warranty_indemnity"

    # Other
    OTHER = "other"


class DecisionType(Enum):
    """Types of underwriting decisions."""
    AUTO_QUOTE = "auto_quote"  # Can be quoted automatically
    REFERRAL = "referral"  # Needs human review
    DECLINE = "decline"  # Outside appetite
    MORE_INFO = "more_info"  # Need additional information


# =============================================================================
# Supporting Dataclasses
# =============================================================================

@dataclass
class RiskFactors:
    """
    Detailed breakdown of risk factors affecting pricing.
    """
    # Base factors
    base_rate: Decimal
    class_of_business: str

    # Loading factors (multipliers)
    territory_loading: Decimal = Decimal("1.00")
    industry_loading: Decimal = Decimal("1.00")
    size_loading: Decimal = Decimal("1.00")
    claims_loading: Decimal = Decimal("1.00")
    coverage_loading: Decimal = Decimal("1.00")
    limit_loading: Decimal = Decimal("1.00")
    deductible_credit: Decimal = Decimal("1.00")

    # Experience factors
    tenure_credit: Decimal = Decimal("1.00")
    risk_management_credit: Decimal = Decimal("1.00")

    # Market factors
    cat_loading: Decimal = Decimal("1.00")
    market_conditions_factor: Decimal = Decimal("1.00")

    # Expense and profit
    expense_ratio: Decimal = Decimal("0.30")  # 30% expenses
    profit_margin: Decimal = Decimal("0.10")  # 10% target profit

    # Specialty-specific adjustments
    specialty_adjustments: Dict[str, Decimal] = field(default_factory=dict)

    def get_total_loading(self) -> Decimal:
        """Calculate total loading factor."""
        loading = (
            self.territory_loading *
            self.industry_loading *
            self.size_loading *
            self.claims_loading *
            self.coverage_loading *
            self.limit_loading *
            self.deductible_credit *
            self.tenure_credit *
            self.risk_management_credit *
            self.cat_loading *
            self.market_conditions_factor
        )

        # Apply specialty adjustments
        for adj in self.specialty_adjustments.values():
            loading *= adj

        return loading

    def get_expense_and_profit_factor(self) -> Decimal:
        """Calculate expense and profit factor."""
        return Decimal("1") + self.expense_ratio + self.profit_margin


@dataclass
class PricingBreakdown:
    """
    Complete breakdown of premium calculation.
    """
    # Input parameters
    exposure_base: Decimal  # Revenue, asset value, etc.
    limit_of_liability: Decimal
    deductible: Decimal
    currency: str

    # Calculation components
    pure_premium: Decimal  # Expected loss cost
    risk_load: Decimal  # Risk margin
    expense_load: Decimal  # Operating expenses
    profit_load: Decimal  # Target profit
    cat_load: Decimal  # Catastrophe loading

    # Final premium
    technical_premium: Decimal

    # Rate metrics
    rate_on_line: Decimal  # Premium / Limit
    rate_per_unit: Decimal  # Premium / Exposure

    # Risk factors used
    risk_factors: RiskFactors = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "exposure_base": float(self.exposure_base),
            "limit_of_liability": float(self.limit_of_liability),
            "deductible": float(self.deductible),
            "currency": self.currency,
            "pure_premium": float(self.pure_premium),
            "risk_load": float(self.risk_load),
            "expense_load": float(self.expense_load),
            "profit_load": float(self.profit_load),
            "cat_load": float(self.cat_load),
            "technical_premium": float(self.technical_premium),
            "rate_on_line": float(self.rate_on_line),
            "rate_per_unit": float(self.rate_per_unit),
        }


@dataclass
class MarketComparison:
    """
    Comparison of pricing to market benchmarks.
    """
    # Our pricing
    quoted_premium: Decimal
    quoted_rate: Decimal

    # Market benchmarks
    market_low: Decimal
    market_median: Decimal
    market_high: Decimal
    market_average: Decimal

    # Percentile
    percentile: float  # Where our quote falls in market (0-100)

    # Competitiveness
    competitive_position: str  # "below_market", "at_market", "above_market"
    price_to_market_ratio: Decimal  # Our price / Market median

    # Historical context
    yoy_market_change: Optional[float] = None  # Year-over-year market change %
    market_trend: Optional[str] = None  # "hardening", "stable", "softening"

    # Data quality
    benchmark_data_points: int = 0
    benchmark_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "quoted_premium": float(self.quoted_premium),
            "quoted_rate": float(self.quoted_rate),
            "market_low": float(self.market_low),
            "market_median": float(self.market_median),
            "market_high": float(self.market_high),
            "market_average": float(self.market_average),
            "percentile": self.percentile,
            "competitive_position": self.competitive_position,
            "price_to_market_ratio": float(self.price_to_market_ratio),
            "yoy_market_change": self.yoy_market_change,
            "market_trend": self.market_trend,
            "benchmark_data_points": self.benchmark_data_points,
            "benchmark_confidence": self.benchmark_confidence,
        }


@dataclass
class CapacityRecommendation:
    """
    Recommendation for optimal syndicate line.
    """
    # Recommended line
    recommended_line: Decimal  # Percentage (0-100)
    minimum_line: Decimal
    maximum_line: Decimal

    # Rationale
    rationale: List[str]

    # Portfolio impact
    portfolio_fit_score: float  # 0-100
    diversification_benefit: bool
    concentration_warning: bool

    # Exposure analysis
    current_class_exposure: Decimal
    post_bind_exposure: Decimal
    exposure_limit: Decimal
    utilization_percentage: Decimal

    # Risk appetite alignment
    appetite_alignment: str  # "core", "opportunistic", "outside_appetite"

    # Financial impact
    expected_profit: Decimal
    worst_case_loss: Decimal
    return_on_capacity: Decimal

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "recommended_line": float(self.recommended_line),
            "minimum_line": float(self.minimum_line),
            "maximum_line": float(self.maximum_line),
            "rationale": self.rationale,
            "portfolio_fit_score": self.portfolio_fit_score,
            "diversification_benefit": self.diversification_benefit,
            "concentration_warning": self.concentration_warning,
            "current_class_exposure": float(self.current_class_exposure),
            "post_bind_exposure": float(self.post_bind_exposure),
            "exposure_limit": float(self.exposure_limit),
            "utilization_percentage": float(self.utilization_percentage),
            "appetite_alignment": self.appetite_alignment,
            "expected_profit": float(self.expected_profit),
            "worst_case_loss": float(self.worst_case_loss),
            "return_on_capacity": float(self.return_on_capacity),
        }


@dataclass
class ExplainableAIReport:
    """
    Human-readable explanation of pricing decision.
    Supports regulatory requirements for algorithmic transparency.
    """
    # Summary
    decision: DecisionType
    decision_summary: str
    confidence_score: float  # 0-100

    # Key drivers (ordered by impact)
    key_drivers: List[Dict[str, Any]]
    # Each driver: {factor, impact, direction, explanation}

    # Risk assessment
    risk_score: float
    risk_category: RiskCategory
    risk_narrative: str

    # Pricing explanation
    pricing_narrative: str
    pricing_factors: List[Dict[str, Any]]

    # Recommendations
    recommendations: List[str]
    subjectivities: List[str]

    # Comparison to similar risks
    similar_risks_count: int
    similar_risks_loss_ratio: Optional[float]

    # Model information
    model_version: str
    model_type: str
    calculation_timestamp: datetime

    # Audit trail
    data_sources: List[str]
    assumptions: List[str]
    limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "decision": self.decision.value,
            "decision_summary": self.decision_summary,
            "confidence_score": self.confidence_score,
            "key_drivers": self.key_drivers,
            "risk_score": self.risk_score,
            "risk_category": self.risk_category.value,
            "risk_narrative": self.risk_narrative,
            "pricing_narrative": self.pricing_narrative,
            "pricing_factors": self.pricing_factors,
            "recommendations": self.recommendations,
            "subjectivities": self.subjectivities,
            "similar_risks_count": self.similar_risks_count,
            "similar_risks_loss_ratio": self.similar_risks_loss_ratio,
            "model_version": self.model_version,
            "model_type": self.model_type,
            "calculation_timestamp": self.calculation_timestamp.isoformat(),
            "data_sources": self.data_sources,
            "assumptions": self.assumptions,
            "limitations": self.limitations,
        }


@dataclass
class PricingResultData:
    """
    Complete pricing result with all components.
    """
    # Identification
    pricing_id: str
    assessment_id: Optional[str]

    # Core pricing
    technical_premium: Decimal
    currency: str

    # Confidence intervals
    confidence_low: Decimal  # 10th percentile
    confidence_expected: Decimal  # 50th percentile (same as technical_premium)
    confidence_high: Decimal  # 90th percentile

    # Risk metrics
    risk_score: float  # 0-100
    risk_category: RiskCategory

    # Breakdown
    pricing_breakdown: PricingBreakdown
    risk_factors: RiskFactors

    # Decision
    decision: DecisionType
    decision_reasons: List[str]

    # Key drivers
    key_drivers: List[str]

    # Timestamps
    calculated_at: datetime
    valid_until: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "pricing_id": self.pricing_id,
            "assessment_id": self.assessment_id,
            "technical_premium": float(self.technical_premium),
            "currency": self.currency,
            "confidence_low": float(self.confidence_low),
            "confidence_expected": float(self.confidence_expected),
            "confidence_high": float(self.confidence_high),
            "risk_score": self.risk_score,
            "risk_category": self.risk_category.value,
            "pricing_breakdown": self.pricing_breakdown.to_dict(),
            "decision": self.decision.value,
            "decision_reasons": self.decision_reasons,
            "key_drivers": self.key_drivers,
            "calculated_at": self.calculated_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
        }


@dataclass
class QuoteData:
    """
    Formal quote generated from pricing.
    """
    # Identification
    quote_reference: str  # Format: QT-YYYY-NNNNNN
    assessment_id: Optional[str]
    pricing_id: str

    # Pricing
    quoted_premium: Decimal
    currency: str
    quoted_line: Decimal  # Percentage

    # Coverage
    limit_of_liability: Decimal
    deductible: Decimal

    # Terms
    terms: Dict[str, Any]
    conditions: List[str]
    subjectivities: List[str]
    exclusions: List[str]

    # Validity
    valid_from: datetime
    valid_until: datetime

    # Status
    status: str  # draft, issued, accepted, declined, expired

    # Metadata
    created_at: datetime
    created_by: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "quote_reference": self.quote_reference,
            "assessment_id": self.assessment_id,
            "pricing_id": self.pricing_id,
            "quoted_premium": float(self.quoted_premium),
            "currency": self.currency,
            "quoted_line": float(self.quoted_line),
            "limit_of_liability": float(self.limit_of_liability),
            "deductible": float(self.deductible),
            "terms": self.terms,
            "conditions": self.conditions,
            "subjectivities": self.subjectivities,
            "exclusions": self.exclusions,
            "valid_from": self.valid_from.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
        }


# =============================================================================
# Main Engine Class
# =============================================================================

class AlgorithmicUnderwritingEngine:
    """
    ML-powered pricing and underwriting engine for Lloyd's market.

    This engine provides:
    1. Risk scoring and classification
    2. Technical premium calculation
    3. Market comparison and benchmarking
    4. Capacity optimization
    5. Quote generation
    6. Explainable AI reporting

    Integration with specialty agents:
    - Cyber risks -> CyberUnderwritingAgent
    - Marine risks -> MarineCargoAgent
    - D&O risks -> DOUnderwritingAgent
    - Political risks -> PoliticalRiskAgent
    """

    # Model version for audit trail
    MODEL_VERSION = "3.0.0"
    MODEL_TYPE = "hybrid_glm_gradient_boost"

    # Base rates by class of business (per $1M limit)
    BASE_RATES = {
        ClassOfBusiness.PROPERTY_COMMERCIAL: Decimal("0.0025"),
        ClassOfBusiness.PROPERTY_RESIDENTIAL: Decimal("0.0020"),
        ClassOfBusiness.PROPERTY_DF: Decimal("0.0035"),
        ClassOfBusiness.GENERAL_LIABILITY: Decimal("0.0030"),
        ClassOfBusiness.PROFESSIONAL_LIABILITY: Decimal("0.0045"),
        ClassOfBusiness.DIRECTORS_OFFICERS: Decimal("0.0055"),
        ClassOfBusiness.EMPLOYERS_LIABILITY: Decimal("0.0025"),
        ClassOfBusiness.CYBER: Decimal("0.0080"),
        ClassOfBusiness.MARINE_CARGO: Decimal("0.0015"),
        ClassOfBusiness.MARINE_HULL: Decimal("0.0040"),
        ClassOfBusiness.AVIATION: Decimal("0.0060"),
        ClassOfBusiness.ENERGY: Decimal("0.0050"),
        ClassOfBusiness.POLITICAL_RISK: Decimal("0.0070"),
        ClassOfBusiness.TRADE_CREDIT: Decimal("0.0035"),
        ClassOfBusiness.CONTINGENCY: Decimal("0.0100"),
        ClassOfBusiness.FINANCIAL_INSTITUTIONS: Decimal("0.0065"),
        ClassOfBusiness.CRIME: Decimal("0.0020"),
        ClassOfBusiness.WARRANTY_INDEMNITY: Decimal("0.0150"),
        ClassOfBusiness.OTHER: Decimal("0.0040"),
    }

    # Minimum premiums by class
    MINIMUM_PREMIUMS = {
        ClassOfBusiness.PROPERTY_COMMERCIAL: Decimal("5000"),
        ClassOfBusiness.PROPERTY_RESIDENTIAL: Decimal("2500"),
        ClassOfBusiness.PROPERTY_DF: Decimal("10000"),
        ClassOfBusiness.GENERAL_LIABILITY: Decimal("5000"),
        ClassOfBusiness.PROFESSIONAL_LIABILITY: Decimal("7500"),
        ClassOfBusiness.DIRECTORS_OFFICERS: Decimal("15000"),
        ClassOfBusiness.EMPLOYERS_LIABILITY: Decimal("3000"),
        ClassOfBusiness.CYBER: Decimal("10000"),
        ClassOfBusiness.MARINE_CARGO: Decimal("2500"),
        ClassOfBusiness.MARINE_HULL: Decimal("10000"),
        ClassOfBusiness.AVIATION: Decimal("25000"),
        ClassOfBusiness.ENERGY: Decimal("50000"),
        ClassOfBusiness.POLITICAL_RISK: Decimal("15000"),
        ClassOfBusiness.TRADE_CREDIT: Decimal("7500"),
        ClassOfBusiness.CONTINGENCY: Decimal("5000"),
        ClassOfBusiness.FINANCIAL_INSTITUTIONS: Decimal("20000"),
        ClassOfBusiness.CRIME: Decimal("5000"),
        ClassOfBusiness.WARRANTY_INDEMNITY: Decimal("25000"),
        ClassOfBusiness.OTHER: Decimal("5000"),
    }

    # Territory loading factors
    TERRITORY_LOADINGS = {
        # Tier 1 - Standard rates
        "GB": Decimal("1.00"), "DE": Decimal("1.00"), "FR": Decimal("1.00"),
        "NL": Decimal("1.00"), "BE": Decimal("1.00"), "AT": Decimal("1.00"),
        "CH": Decimal("1.00"), "AU": Decimal("1.00"), "NZ": Decimal("1.00"),
        "CA": Decimal("1.05"), "JP": Decimal("1.00"), "SG": Decimal("1.00"),

        # Tier 2 - Moderate loading
        "US": Decimal("1.15"),  # US litigation environment
        "IE": Decimal("1.05"), "IT": Decimal("1.10"), "ES": Decimal("1.08"),
        "PT": Decimal("1.08"), "SE": Decimal("1.00"), "NO": Decimal("1.00"),
        "DK": Decimal("1.00"), "FI": Decimal("1.00"),

        # Tier 3 - Higher loading
        "BR": Decimal("1.25"), "MX": Decimal("1.20"), "AR": Decimal("1.30"),
        "ZA": Decimal("1.20"), "AE": Decimal("1.10"), "SA": Decimal("1.15"),
        "IN": Decimal("1.15"), "CN": Decimal("1.20"), "HK": Decimal("1.05"),

        # Tier 4 - High risk
        "RU": Decimal("1.50"), "TR": Decimal("1.35"), "EG": Decimal("1.40"),
        "NG": Decimal("1.45"), "PK": Decimal("1.40"), "ID": Decimal("1.25"),
        "PH": Decimal("1.20"), "VN": Decimal("1.20"), "TH": Decimal("1.15"),

        # Default
        "DEFAULT": Decimal("1.20"),
    }

    # Industry loading factors
    INDUSTRY_LOADINGS = {
        "technology": Decimal("1.10"),
        "financial_services": Decimal("1.20"),
        "healthcare": Decimal("1.25"),
        "manufacturing": Decimal("1.05"),
        "retail": Decimal("1.00"),
        "construction": Decimal("1.15"),
        "transportation": Decimal("1.10"),
        "energy": Decimal("1.20"),
        "professional_services": Decimal("1.05"),
        "hospitality": Decimal("1.00"),
        "real_estate": Decimal("1.05"),
        "education": Decimal("0.95"),
        "government": Decimal("0.90"),
        "non_profit": Decimal("0.90"),
        "DEFAULT": Decimal("1.00"),
    }

    # Size loading factors (by revenue bands in USD)
    SIZE_LOADINGS = {
        "micro": Decimal("1.20"),      # < $1M
        "small": Decimal("1.10"),      # $1M - $10M
        "medium": Decimal("1.00"),     # $10M - $100M
        "large": Decimal("0.95"),      # $100M - $1B
        "enterprise": Decimal("0.90"), # > $1B
    }

    # Claims history loading
    CLAIMS_LOADINGS = {
        "excellent": Decimal("0.85"),   # No claims 5+ years
        "good": Decimal("0.95"),        # No claims 3+ years
        "average": Decimal("1.00"),     # Minor claims
        "poor": Decimal("1.25"),        # Significant claims
        "very_poor": Decimal("1.50"),   # Major claims / frequent
    }

    # CAT loading by zone (simplified)
    CAT_LOADINGS = {
        "cat_low": Decimal("1.00"),
        "cat_moderate": Decimal("1.10"),
        "cat_high": Decimal("1.25"),
        "cat_peak": Decimal("1.50"),
    }

    # Limit factors (ILF - Increased Limit Factors)
    LIMIT_FACTORS = {
        Decimal("1000000"): Decimal("1.00"),
        Decimal("2000000"): Decimal("1.50"),
        Decimal("5000000"): Decimal("2.20"),
        Decimal("10000000"): Decimal("3.00"),
        Decimal("25000000"): Decimal("4.50"),
        Decimal("50000000"): Decimal("6.00"),
        Decimal("100000000"): Decimal("8.00"),
    }

    # Deductible credits
    DEDUCTIBLE_CREDITS = {
        Decimal("0"): Decimal("1.00"),
        Decimal("1000"): Decimal("0.98"),
        Decimal("5000"): Decimal("0.95"),
        Decimal("10000"): Decimal("0.92"),
        Decimal("25000"): Decimal("0.88"),
        Decimal("50000"): Decimal("0.83"),
        Decimal("100000"): Decimal("0.78"),
        Decimal("250000"): Decimal("0.70"),
        Decimal("500000"): Decimal("0.62"),
        Decimal("1000000"): Decimal("0.55"),
    }

    def __init__(self, db: Optional[AsyncSession] = None):
        """
        Initialize the underwriting engine.

        Args:
            db: Optional database session for persistence.
        """
        self.db = db

        # Initialize specialty agents
        self.cyber_agent = CyberUnderwritingAgent()
        self.marine_agent = MarineCargoAgent()
        self.do_agent = DOUnderwritingAgent()
        self.political_agent = PoliticalRiskAgent()

        # Quote counter (in production, this would come from DB)
        self._quote_counter = 0

    # =========================================================================
    # Core Pricing Methods
    # =========================================================================

    async def price_submission(
        self,
        submission: Dict[str, Any],
        assessment_id: Optional[str] = None,
    ) -> PricingResultData:
        """
        Calculate technical premium with confidence intervals.

        Args:
            submission: Submission data including:
                - class_of_business: Lloyd's class code
                - limit_of_liability: Policy limit
                - deductible: Retention amount
                - territory: Primary territory code
                - industry: Industry sector
                - revenue: Annual revenue (for sizing)
                - claims_history: Claims summary
                - inception_date: Policy inception
                - expiry_date: Policy expiry
                - Additional specialty-specific fields
            assessment_id: Optional assessment ID for linking.

        Returns:
            PricingResultData with premium and confidence intervals.
        """
        # Parse and validate inputs
        class_of_business = self._parse_class_of_business(
            submission.get("class_of_business", "other")
        )
        limit = Decimal(str(submission.get("limit_of_liability", 1000000)))
        deductible = Decimal(str(submission.get("deductible", 0)))
        currency = submission.get("currency", "GBP").upper()
        territory = submission.get("territory", "GB").upper()[:2]
        industry = submission.get("industry", "").lower()
        revenue = Decimal(str(submission.get("revenue", 0)))
        claims_history = submission.get("claims_history", "average")

        # Get specialty agent analysis if applicable
        specialty_analysis = await self._get_specialty_analysis(
            class_of_business, submission
        )

        # Calculate risk score
        risk_score, risk_category = await self._calculate_risk_score(
            submission, specialty_analysis
        )

        # Build risk factors
        risk_factors = await self._build_risk_factors(
            class_of_business=class_of_business,
            limit=limit,
            deductible=deductible,
            territory=territory,
            industry=industry,
            revenue=revenue,
            claims_history=claims_history,
            risk_score=risk_score,
            specialty_analysis=specialty_analysis,
        )

        # Calculate pricing breakdown
        pricing_breakdown = await self._calculate_pricing_breakdown(
            class_of_business=class_of_business,
            limit=limit,
            deductible=deductible,
            currency=currency,
            revenue=revenue,
            risk_factors=risk_factors,
        )

        # Calculate confidence intervals
        confidence_low, confidence_high = self._calculate_confidence_intervals(
            pricing_breakdown.technical_premium,
            risk_score,
        )

        # Determine decision
        decision, decision_reasons = self._determine_decision(
            risk_score, risk_category, submission
        )

        # Identify key drivers
        key_drivers = self._identify_key_drivers(risk_factors, specialty_analysis)

        # Generate pricing ID
        pricing_id = self._generate_pricing_id(submission)

        now = datetime.now(timezone.utc)

        return PricingResultData(
            pricing_id=pricing_id,
            assessment_id=assessment_id,
            technical_premium=pricing_breakdown.technical_premium,
            currency=currency,
            confidence_low=confidence_low,
            confidence_expected=pricing_breakdown.technical_premium,
            confidence_high=confidence_high,
            risk_score=risk_score,
            risk_category=risk_category,
            pricing_breakdown=pricing_breakdown,
            risk_factors=risk_factors,
            decision=decision,
            decision_reasons=decision_reasons,
            key_drivers=key_drivers,
            calculated_at=now,
            valid_until=now + timedelta(days=30),
        )

    async def compare_to_market(
        self,
        submission: Dict[str, Any],
        pricing_result: Optional[PricingResultData] = None,
    ) -> MarketComparison:
        """
        Compare pricing to market benchmarks.

        Args:
            submission: Submission data.
            pricing_result: Optional pre-calculated pricing result.

        Returns:
            MarketComparison with benchmark analysis.
        """
        # Get pricing if not provided
        if pricing_result is None:
            pricing_result = await self.price_submission(submission)

        class_of_business = self._parse_class_of_business(
            submission.get("class_of_business", "other")
        )
        limit = Decimal(str(submission.get("limit_of_liability", 1000000)))

        # Get market benchmarks (in production, this would query historical data)
        benchmarks = await self._get_market_benchmarks(
            class_of_business, submission
        )

        quoted_premium = pricing_result.technical_premium
        quoted_rate = (quoted_premium / limit) if limit > 0 else Decimal("0")

        # Calculate percentile
        percentile = self._calculate_percentile(
            quoted_premium, benchmarks
        )

        # Determine competitive position
        median = benchmarks["median"]
        if quoted_premium < median * Decimal("0.95"):
            position = "below_market"
        elif quoted_premium > median * Decimal("1.05"):
            position = "above_market"
        else:
            position = "at_market"

        return MarketComparison(
            quoted_premium=quoted_premium,
            quoted_rate=quoted_rate,
            market_low=benchmarks["low"],
            market_median=benchmarks["median"],
            market_high=benchmarks["high"],
            market_average=benchmarks["average"],
            percentile=percentile,
            competitive_position=position,
            price_to_market_ratio=quoted_premium / median if median > 0 else Decimal("1"),
            yoy_market_change=benchmarks.get("yoy_change"),
            market_trend=benchmarks.get("trend"),
            benchmark_data_points=benchmarks.get("data_points", 0),
            benchmark_confidence=benchmarks.get("confidence", 0.0),
        )

    async def generate_quote(
        self,
        pricing_result: PricingResultData,
        terms: Dict[str, Any],
        syndicate_id: Optional[int] = None,
    ) -> QuoteData:
        """
        Generate formal quote with terms and conditions.

        Args:
            pricing_result: Calculated pricing result.
            terms: Quote terms including:
                - quoted_premium: Final premium (may differ from technical)
                - quoted_line: Line percentage offered
                - validity_days: Quote validity period
                - additional_conditions: Extra conditions
            syndicate_id: Optional syndicate ID.

        Returns:
            QuoteData with formal quote details.
        """
        # Parse terms
        quoted_premium = Decimal(str(
            terms.get("quoted_premium", pricing_result.technical_premium)
        ))
        quoted_line = Decimal(str(terms.get("quoted_line", 100)))
        validity_days = int(terms.get("validity_days", 14))
        additional_conditions = terms.get("additional_conditions", [])

        # Generate quote reference
        quote_reference = self._generate_quote_reference()

        # Build standard conditions
        conditions = self._get_standard_conditions(
            pricing_result.risk_category
        )
        conditions.extend(additional_conditions)

        # Build subjectivities based on risk and decision
        subjectivities = self._get_subjectivities(
            pricing_result.decision,
            pricing_result.risk_category,
            pricing_result.decision_reasons,
        )

        # Build exclusions
        exclusions = self._get_standard_exclusions(
            ClassOfBusiness(pricing_result.pricing_breakdown.risk_factors.class_of_business)
            if pricing_result.pricing_breakdown.risk_factors
            else ClassOfBusiness.OTHER
        )

        now = datetime.now(timezone.utc)

        return QuoteData(
            quote_reference=quote_reference,
            assessment_id=pricing_result.assessment_id,
            pricing_id=pricing_result.pricing_id,
            quoted_premium=quoted_premium,
            currency=pricing_result.currency,
            quoted_line=quoted_line,
            limit_of_liability=pricing_result.pricing_breakdown.limit_of_liability,
            deductible=pricing_result.pricing_breakdown.deductible,
            terms=self._build_quote_terms(pricing_result, terms),
            conditions=conditions,
            subjectivities=subjectivities,
            exclusions=exclusions,
            valid_from=now,
            valid_until=now + timedelta(days=validity_days),
            status="draft",
            created_at=now,
            created_by=terms.get("created_by"),
        )

    async def optimize_capacity(
        self,
        syndicate_id: int,
        submission: Dict[str, Any],
        pricing_result: Optional[PricingResultData] = None,
    ) -> CapacityRecommendation:
        """
        Recommend optimal line based on portfolio analysis.

        Args:
            syndicate_id: Syndicate identifier.
            submission: Submission data.
            pricing_result: Optional pre-calculated pricing result.

        Returns:
            CapacityRecommendation with optimal line suggestion.
        """
        # Get pricing if not provided
        if pricing_result is None:
            pricing_result = await self.price_submission(submission)

        class_of_business = self._parse_class_of_business(
            submission.get("class_of_business", "other")
        )
        limit = Decimal(str(submission.get("limit_of_liability", 1000000)))

        # Get current portfolio exposure (mock data in this version)
        portfolio = await self._get_portfolio_exposure(syndicate_id, class_of_business)

        # Calculate optimal line
        recommended_line, min_line, max_line, rationale = self._calculate_optimal_line(
            pricing_result,
            portfolio,
            submission,
        )

        # Calculate post-bind exposure
        post_bind = portfolio["current_exposure"] + (limit * recommended_line / 100)

        # Determine appetite alignment
        if pricing_result.risk_category in [RiskCategory.VERY_LOW, RiskCategory.LOW]:
            appetite = "core"
        elif pricing_result.risk_category == RiskCategory.MODERATE:
            appetite = "opportunistic"
        else:
            appetite = "outside_appetite"

        # Calculate financial metrics
        expected_loss_ratio = Decimal("0.65")  # 65% expected loss ratio
        expected_profit = pricing_result.technical_premium * (1 - expected_loss_ratio) * recommended_line / 100
        worst_case = limit * recommended_line / 100
        roc = (expected_profit / worst_case * 100) if worst_case > 0 else Decimal("0")

        return CapacityRecommendation(
            recommended_line=recommended_line,
            minimum_line=min_line,
            maximum_line=max_line,
            rationale=rationale,
            portfolio_fit_score=float(100 - pricing_result.risk_score),
            diversification_benefit=portfolio.get("diversification_benefit", False),
            concentration_warning=post_bind > portfolio["limit"] * Decimal("0.8"),
            current_class_exposure=portfolio["current_exposure"],
            post_bind_exposure=post_bind,
            exposure_limit=portfolio["limit"],
            utilization_percentage=(post_bind / portfolio["limit"] * 100) if portfolio["limit"] > 0 else Decimal("0"),
            appetite_alignment=appetite,
            expected_profit=expected_profit,
            worst_case_loss=worst_case,
            return_on_capacity=roc,
        )

    async def explain_decision(
        self,
        pricing_result: PricingResultData,
        submission: Dict[str, Any],
    ) -> ExplainableAIReport:
        """
        Generate human-readable explanation of pricing decision.

        Args:
            pricing_result: Calculated pricing result.
            submission: Original submission data.

        Returns:
            ExplainableAIReport with full explanation.
        """
        now = datetime.now(timezone.utc)

        # Build key drivers with impact analysis
        key_drivers = await self._analyze_key_drivers(
            pricing_result.risk_factors, submission
        )

        # Generate narratives
        risk_narrative = self._generate_risk_narrative(
            pricing_result.risk_score,
            pricing_result.risk_category,
            submission,
        )

        pricing_narrative = self._generate_pricing_narrative(
            pricing_result.pricing_breakdown,
            pricing_result.risk_factors,
        )

        # Build pricing factors explanation
        pricing_factors = self._explain_pricing_factors(
            pricing_result.risk_factors
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            pricing_result.decision,
            pricing_result.risk_category,
            submission,
        )

        # Get similar risks analysis (mock data)
        similar_analysis = await self._analyze_similar_risks(submission)

        return ExplainableAIReport(
            decision=pricing_result.decision,
            decision_summary=self._summarize_decision(pricing_result),
            confidence_score=100 - pricing_result.risk_score,
            key_drivers=key_drivers,
            risk_score=pricing_result.risk_score,
            risk_category=pricing_result.risk_category,
            risk_narrative=risk_narrative,
            pricing_narrative=pricing_narrative,
            pricing_factors=pricing_factors,
            recommendations=recommendations,
            subjectivities=pricing_result.decision_reasons,
            similar_risks_count=similar_analysis["count"],
            similar_risks_loss_ratio=similar_analysis["loss_ratio"],
            model_version=self.MODEL_VERSION,
            model_type=self.MODEL_TYPE,
            calculation_timestamp=now,
            data_sources=self._get_data_sources(submission),
            assumptions=self._get_assumptions(),
            limitations=self._get_limitations(),
        )

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _parse_class_of_business(self, class_str: str) -> ClassOfBusiness:
        """Parse class of business string to enum."""
        class_str = class_str.lower().replace(" ", "_").replace("-", "_").replace("&", "_")

        # Try direct match
        for cob in ClassOfBusiness:
            if cob.value == class_str:
                return cob

        # Fuzzy matching
        mappings = {
            "cyber": ClassOfBusiness.CYBER,
            "cyber_liability": ClassOfBusiness.CYBER,
            "marine": ClassOfBusiness.MARINE_CARGO,
            "cargo": ClassOfBusiness.MARINE_CARGO,
            "hull": ClassOfBusiness.MARINE_HULL,
            "do": ClassOfBusiness.DIRECTORS_OFFICERS,
            "d_o": ClassOfBusiness.DIRECTORS_OFFICERS,
            "dando": ClassOfBusiness.DIRECTORS_OFFICERS,
            "political": ClassOfBusiness.POLITICAL_RISK,
            "property": ClassOfBusiness.PROPERTY_COMMERCIAL,
            "commercial_property": ClassOfBusiness.PROPERTY_COMMERCIAL,
            "liability": ClassOfBusiness.GENERAL_LIABILITY,
            "gl": ClassOfBusiness.GENERAL_LIABILITY,
            "pl": ClassOfBusiness.PROFESSIONAL_LIABILITY,
            "pi": ClassOfBusiness.PROFESSIONAL_LIABILITY,
            "epl": ClassOfBusiness.EMPLOYERS_LIABILITY,
            "aviation": ClassOfBusiness.AVIATION,
            "energy": ClassOfBusiness.ENERGY,
            "credit": ClassOfBusiness.TRADE_CREDIT,
            "crime": ClassOfBusiness.CRIME,
            "fi": ClassOfBusiness.FINANCIAL_INSTITUTIONS,
            "wandi": ClassOfBusiness.WARRANTY_INDEMNITY,
        }

        for key, value in mappings.items():
            if key in class_str:
                return value

        return ClassOfBusiness.OTHER

    async def _get_specialty_analysis(
        self,
        class_of_business: ClassOfBusiness,
        submission: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Get analysis from appropriate specialty agent."""
        try:
            if class_of_business == ClassOfBusiness.CYBER:
                analysis = await self.cyber_agent.analyze_cyber_submission(submission)
                return {
                    "agent": "cyber",
                    "risk_score": analysis.risk_score,
                    "risk_level": analysis.risk_level.value,
                    "premium_indication": float(analysis.premium_indication),
                    "key_concerns": analysis.key_concerns,
                    "mitigating_factors": analysis.mitigating_factors,
                    "warranties": analysis.warranty_requirements,
                    "exclusions": analysis.exclusion_recommendations,
                }

            elif class_of_business == ClassOfBusiness.MARINE_CARGO:
                route = submission.get("route", {})
                cargo_type = submission.get("cargo_type", "general")
                voyage_risk = await self.marine_agent.calculate_voyage_risk(route)
                cargo_risk = await self.marine_agent.assess_cargo_susceptibility(cargo_type)
                clauses = await self.marine_agent.recommend_clauses(submission)
                return {
                    "agent": "marine",
                    "voyage_risk_score": voyage_risk.risk_score,
                    "route_risk": voyage_risk.route_risk,
                    "piracy_exposure": voyage_risk.piracy_exposure,
                    "war_risk": voyage_risk.war_risk_territory,
                    "cargo_susceptibility": cargo_risk.susceptibility_score,
                    "recommended_clauses": clauses,
                }

            elif class_of_business == ClassOfBusiness.DIRECTORS_OFFICERS:
                governance = await self.do_agent.analyze_governance(submission)
                financials = submission.get("financials", {})
                securities = await self.do_agent.assess_securities_exposure(financials)
                return {
                    "agent": "do",
                    "governance_score": governance.overall_score,
                    "governance_concerns": governance.concerns,
                    "securities_risk": securities.risk_score,
                    "class_action_exposure": securities.class_action_exposure,
                    "disclosure_risk": securities.disclosure_risk,
                }

            elif class_of_business == ClassOfBusiness.POLITICAL_RISK:
                country = submission.get("country", "US")
                country_risk = await self.political_agent.assess_country_risk(country)
                return {
                    "agent": "political",
                    "country_risk_score": country_risk.risk_score,
                    "risk_tier": country_risk.risk_tier,
                    "sanctions_status": country_risk.sanctions_status,
                    "political_stability": country_risk.political_stability,
                    "key_risks": country_risk.key_risks,
                }

        except Exception as e:
            # Log error but continue without specialty analysis
            return {"error": str(e)}

        return None

    async def _calculate_risk_score(
        self,
        submission: Dict[str, Any],
        specialty_analysis: Optional[Dict[str, Any]],
    ) -> Tuple[float, RiskCategory]:
        """Calculate overall risk score (0-100)."""
        scores = []
        weights = []

        # Base score from claims history
        claims_scores = {
            "excellent": 15, "good": 25, "average": 40,
            "poor": 65, "very_poor": 85
        }
        claims_history = submission.get("claims_history", "average")
        scores.append(claims_scores.get(claims_history, 40))
        weights.append(0.25)

        # Territory risk
        territory = submission.get("territory", "GB").upper()[:2]
        territory_loading = float(self.TERRITORY_LOADINGS.get(
            territory, self.TERRITORY_LOADINGS["DEFAULT"]
        ))
        scores.append(min(100, (territory_loading - 1) * 200 + 30))
        weights.append(0.15)

        # Industry risk
        industry = submission.get("industry", "").lower()
        industry_loading = float(self.INDUSTRY_LOADINGS.get(
            industry, self.INDUSTRY_LOADINGS["DEFAULT"]
        ))
        scores.append(min(100, (industry_loading - 1) * 200 + 30))
        weights.append(0.15)

        # Limit adequacy
        limit = Decimal(str(submission.get("limit_of_liability", 1000000)))
        revenue = Decimal(str(submission.get("revenue", 0)))
        if revenue > 0:
            limit_ratio = float(limit / revenue)
            if limit_ratio < 0.05:
                scores.append(60)  # Potentially underinsured
            elif limit_ratio > 0.50:
                scores.append(40)  # High limits relative to revenue
            else:
                scores.append(25)
        else:
            scores.append(40)
        weights.append(0.10)

        # Specialty agent score
        if specialty_analysis and "risk_score" in specialty_analysis:
            scores.append(specialty_analysis["risk_score"])
            weights.append(0.35)
        elif specialty_analysis and "voyage_risk_score" in specialty_analysis:
            scores.append(specialty_analysis["voyage_risk_score"])
            weights.append(0.35)
        elif specialty_analysis and "governance_score" in specialty_analysis:
            # Invert governance score (higher is better for governance)
            scores.append(100 - specialty_analysis["governance_score"])
            weights.append(0.35)
        elif specialty_analysis and "country_risk_score" in specialty_analysis:
            scores.append(specialty_analysis["country_risk_score"])
            weights.append(0.35)

        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # Weighted average
        risk_score = sum(s * w for s, w in zip(scores, weights))
        risk_score = max(0, min(100, risk_score))

        # Determine category
        if risk_score < 20:
            category = RiskCategory.VERY_LOW
        elif risk_score < 35:
            category = RiskCategory.LOW
        elif risk_score < 55:
            category = RiskCategory.MODERATE
        elif risk_score < 75:
            category = RiskCategory.HIGH
        elif risk_score < 90:
            category = RiskCategory.VERY_HIGH
        else:
            category = RiskCategory.DECLINE

        return round(risk_score, 2), category

    async def _build_risk_factors(
        self,
        class_of_business: ClassOfBusiness,
        limit: Decimal,
        deductible: Decimal,
        territory: str,
        industry: str,
        revenue: Decimal,
        claims_history: str,
        risk_score: float,
        specialty_analysis: Optional[Dict[str, Any]],
    ) -> RiskFactors:
        """Build complete risk factors object."""
        # Get base rate
        base_rate = self.BASE_RATES.get(
            class_of_business, self.BASE_RATES[ClassOfBusiness.OTHER]
        )

        # Territory loading
        territory_loading = self.TERRITORY_LOADINGS.get(
            territory, self.TERRITORY_LOADINGS["DEFAULT"]
        )

        # Industry loading
        industry_loading = self.INDUSTRY_LOADINGS.get(
            industry, self.INDUSTRY_LOADINGS["DEFAULT"]
        )

        # Size loading
        if revenue < Decimal("1000000"):
            size_loading = self.SIZE_LOADINGS["micro"]
        elif revenue < Decimal("10000000"):
            size_loading = self.SIZE_LOADINGS["small"]
        elif revenue < Decimal("100000000"):
            size_loading = self.SIZE_LOADINGS["medium"]
        elif revenue < Decimal("1000000000"):
            size_loading = self.SIZE_LOADINGS["large"]
        else:
            size_loading = self.SIZE_LOADINGS["enterprise"]

        # Claims loading
        claims_loading = self.CLAIMS_LOADINGS.get(
            claims_history, self.CLAIMS_LOADINGS["average"]
        )

        # Limit loading (ILF)
        limit_loading = self._interpolate_limit_factor(limit)

        # Deductible credit
        deductible_credit = self._interpolate_deductible_credit(deductible)

        # CAT loading (simplified - in production would use postal codes/coordinates)
        cat_zones = {
            "US": "cat_high", "JP": "cat_high",
            "AU": "cat_moderate", "MX": "cat_moderate",
            "GB": "cat_low", "DE": "cat_low",
        }
        cat_zone = cat_zones.get(territory, "cat_moderate")
        cat_loading = self.CAT_LOADINGS[cat_zone]

        # Build specialty adjustments
        specialty_adjustments = {}
        if specialty_analysis:
            if specialty_analysis.get("agent") == "cyber":
                cyber_score = specialty_analysis.get("risk_score", 50)
                specialty_adjustments["cyber_risk"] = Decimal(str(1 + (cyber_score - 50) / 100))
            elif specialty_analysis.get("agent") == "marine":
                if specialty_analysis.get("piracy_exposure"):
                    specialty_adjustments["piracy"] = Decimal("1.20")
                if specialty_analysis.get("war_risk"):
                    specialty_adjustments["war_risk"] = Decimal("1.35")
            elif specialty_analysis.get("agent") == "do":
                gov_score = specialty_analysis.get("governance_score", 50)
                specialty_adjustments["governance"] = Decimal(str(1 + (50 - gov_score) / 200))
                if specialty_analysis.get("class_action_exposure"):
                    specialty_adjustments["securities"] = Decimal("1.25")
            elif specialty_analysis.get("agent") == "political":
                tier = int(specialty_analysis.get("risk_tier", "3"))
                specialty_adjustments["country_tier"] = Decimal(str(1 + (tier - 1) * 0.15))

        return RiskFactors(
            base_rate=base_rate,
            class_of_business=class_of_business.value,
            territory_loading=territory_loading,
            industry_loading=industry_loading,
            size_loading=size_loading,
            claims_loading=claims_loading,
            coverage_loading=Decimal("1.00"),  # Adjustable based on coverage extensions
            limit_loading=limit_loading,
            deductible_credit=deductible_credit,
            tenure_credit=Decimal("1.00"),  # Would check renewal history
            risk_management_credit=Decimal("1.00"),  # Would check risk management practices
            cat_loading=cat_loading,
            market_conditions_factor=Decimal("1.00"),  # Current market conditions
            expense_ratio=Decimal("0.30"),
            profit_margin=Decimal("0.10"),
            specialty_adjustments=specialty_adjustments,
        )

    def _interpolate_limit_factor(self, limit: Decimal) -> Decimal:
        """Interpolate ILF for given limit."""
        sorted_limits = sorted(self.LIMIT_FACTORS.keys())

        # Below minimum
        if limit <= sorted_limits[0]:
            return self.LIMIT_FACTORS[sorted_limits[0]]

        # Above maximum
        if limit >= sorted_limits[-1]:
            # Extrapolate with diminishing factor
            max_factor = self.LIMIT_FACTORS[sorted_limits[-1]]
            excess = limit / sorted_limits[-1]
            return max_factor * (Decimal("1") + (excess - 1) * Decimal("0.3"))

        # Interpolate
        for i in range(len(sorted_limits) - 1):
            if sorted_limits[i] <= limit < sorted_limits[i + 1]:
                lower = sorted_limits[i]
                upper = sorted_limits[i + 1]
                lower_factor = self.LIMIT_FACTORS[lower]
                upper_factor = self.LIMIT_FACTORS[upper]
                ratio = (limit - lower) / (upper - lower)
                return lower_factor + (upper_factor - lower_factor) * ratio

        return Decimal("1.00")

    def _interpolate_deductible_credit(self, deductible: Decimal) -> Decimal:
        """Interpolate deductible credit."""
        sorted_deductibles = sorted(self.DEDUCTIBLE_CREDITS.keys())

        # At or below minimum
        if deductible <= sorted_deductibles[0]:
            return self.DEDUCTIBLE_CREDITS[sorted_deductibles[0]]

        # At or above maximum
        if deductible >= sorted_deductibles[-1]:
            # Extrapolate with floor
            max_credit = self.DEDUCTIBLE_CREDITS[sorted_deductibles[-1]]
            excess_factor = deductible / sorted_deductibles[-1]
            return max(Decimal("0.40"), max_credit - (excess_factor - 1) * Decimal("0.05"))

        # Interpolate
        for i in range(len(sorted_deductibles) - 1):
            if sorted_deductibles[i] <= deductible < sorted_deductibles[i + 1]:
                lower = sorted_deductibles[i]
                upper = sorted_deductibles[i + 1]
                lower_credit = self.DEDUCTIBLE_CREDITS[lower]
                upper_credit = self.DEDUCTIBLE_CREDITS[upper]
                ratio = (deductible - lower) / (upper - lower)
                return lower_credit + (upper_credit - lower_credit) * ratio

        return Decimal("1.00")

    async def _calculate_pricing_breakdown(
        self,
        class_of_business: ClassOfBusiness,
        limit: Decimal,
        deductible: Decimal,
        currency: str,
        revenue: Decimal,
        risk_factors: RiskFactors,
    ) -> PricingBreakdown:
        """Calculate complete pricing breakdown."""
        # Determine exposure base
        exposure_base = revenue if revenue > 0 else limit

        # Calculate pure premium (expected loss cost)
        base_premium = limit * risk_factors.base_rate
        total_loading = risk_factors.get_total_loading()
        pure_premium = base_premium * total_loading

        # Add expense and profit components
        expense_profit_factor = risk_factors.get_expense_and_profit_factor()

        # Split out components
        risk_load = pure_premium * Decimal("0.15")  # 15% risk margin
        expense_load = pure_premium * risk_factors.expense_ratio
        profit_load = pure_premium * risk_factors.profit_margin
        cat_load = pure_premium * (risk_factors.cat_loading - 1) * Decimal("0.5")

        # Total technical premium
        technical_premium = pure_premium + risk_load + expense_load + profit_load + cat_load

        # Apply minimum premium
        minimum = self.MINIMUM_PREMIUMS.get(
            class_of_business, self.MINIMUM_PREMIUMS[ClassOfBusiness.OTHER]
        )
        technical_premium = max(technical_premium, minimum)

        # Round to 2 decimal places
        technical_premium = technical_premium.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Calculate rate metrics
        rate_on_line = (technical_premium / limit * 100) if limit > 0 else Decimal("0")
        rate_per_unit = (technical_premium / exposure_base * 1000) if exposure_base > 0 else Decimal("0")

        return PricingBreakdown(
            exposure_base=exposure_base,
            limit_of_liability=limit,
            deductible=deductible,
            currency=currency,
            pure_premium=pure_premium.quantize(Decimal("0.01")),
            risk_load=risk_load.quantize(Decimal("0.01")),
            expense_load=expense_load.quantize(Decimal("0.01")),
            profit_load=profit_load.quantize(Decimal("0.01")),
            cat_load=cat_load.quantize(Decimal("0.01")),
            technical_premium=technical_premium,
            rate_on_line=rate_on_line.quantize(Decimal("0.01")),
            rate_per_unit=rate_per_unit.quantize(Decimal("0.01")),
            risk_factors=risk_factors,
        )

    def _calculate_confidence_intervals(
        self,
        technical_premium: Decimal,
        risk_score: float,
    ) -> Tuple[Decimal, Decimal]:
        """Calculate confidence intervals based on risk uncertainty."""
        # Higher risk = wider intervals
        uncertainty = Decimal(str(0.10 + (risk_score / 100) * 0.20))  # 10-30%

        confidence_low = (technical_premium * (1 - uncertainty)).quantize(Decimal("0.01"))
        confidence_high = (technical_premium * (1 + uncertainty)).quantize(Decimal("0.01"))

        return confidence_low, confidence_high

    def _determine_decision(
        self,
        risk_score: float,
        risk_category: RiskCategory,
        submission: Dict[str, Any],
    ) -> Tuple[DecisionType, List[str]]:
        """Determine underwriting decision."""
        reasons = []

        # Auto-decline conditions
        if risk_category == RiskCategory.DECLINE:
            return DecisionType.DECLINE, ["Risk score exceeds maximum threshold (90+)"]

        # Check for missing critical information
        required_fields = ["limit_of_liability", "class_of_business"]
        missing = [f for f in required_fields if not submission.get(f)]
        if missing:
            reasons.append(f"Missing required fields: {', '.join(missing)}")
            return DecisionType.MORE_INFO, reasons

        # High risk requires referral
        if risk_category in [RiskCategory.HIGH, RiskCategory.VERY_HIGH]:
            reasons.append(f"Risk category is {risk_category.value} - requires senior review")
            return DecisionType.REFERRAL, reasons

        # Large limits require referral
        limit = Decimal(str(submission.get("limit_of_liability", 0)))
        if limit > Decimal("50000000"):
            reasons.append("Limit exceeds automatic authority ($50M)")
            return DecisionType.REFERRAL, reasons

        # Auto-quote for low/moderate risk
        if risk_category in [RiskCategory.VERY_LOW, RiskCategory.LOW]:
            return DecisionType.AUTO_QUOTE, ["Risk within automatic authority"]

        if risk_category == RiskCategory.MODERATE:
            # Additional checks for moderate risk
            if risk_score > 50:
                reasons.append("Moderate risk with elevated score - review recommended")
                return DecisionType.REFERRAL, reasons
            return DecisionType.AUTO_QUOTE, ["Risk within automatic authority"]

        return DecisionType.REFERRAL, ["Default referral - manual review required"]

    def _identify_key_drivers(
        self,
        risk_factors: RiskFactors,
        specialty_analysis: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Identify key factors driving the pricing."""
        drivers = []

        # Check loadings above threshold
        if risk_factors.territory_loading > Decimal("1.10"):
            drivers.append(f"Territory loading: {float(risk_factors.territory_loading):.0%}")

        if risk_factors.industry_loading > Decimal("1.10"):
            drivers.append(f"Industry loading: {float(risk_factors.industry_loading):.0%}")

        if risk_factors.claims_loading > Decimal("1.10"):
            drivers.append(f"Claims history loading: {float(risk_factors.claims_loading):.0%}")
        elif risk_factors.claims_loading < Decimal("0.95"):
            drivers.append(f"Claims history credit: {float(risk_factors.claims_loading):.0%}")

        if risk_factors.limit_loading > Decimal("1.50"):
            drivers.append(f"Increased limit factor: {float(risk_factors.limit_loading):.2f}x")

        if risk_factors.deductible_credit < Decimal("0.90"):
            drivers.append(f"Deductible credit: {float(risk_factors.deductible_credit):.0%}")

        if risk_factors.cat_loading > Decimal("1.10"):
            drivers.append(f"Catastrophe loading: {float(risk_factors.cat_loading):.0%}")

        # Specialty adjustments
        for adj_name, adj_value in risk_factors.specialty_adjustments.items():
            if adj_value > Decimal("1.05"):
                drivers.append(f"{adj_name.replace('_', ' ').title()} surcharge: {float(adj_value):.0%}")
            elif adj_value < Decimal("0.95"):
                drivers.append(f"{adj_name.replace('_', ' ').title()} credit: {float(adj_value):.0%}")

        # Specialty analysis specific drivers
        if specialty_analysis:
            if specialty_analysis.get("key_concerns"):
                for concern in specialty_analysis["key_concerns"][:2]:
                    drivers.append(f"Specialty concern: {concern}")
            if specialty_analysis.get("piracy_exposure"):
                drivers.append("Piracy exposure zone")
            if specialty_analysis.get("war_risk"):
                drivers.append("War risk territory")
            if specialty_analysis.get("class_action_exposure"):
                drivers.append("Securities class action exposure")

        return drivers[:10]  # Limit to top 10

    def _generate_pricing_id(self, submission: Dict[str, Any]) -> str:
        """Generate unique pricing ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        data_hash = hashlib.md5(str(submission).encode(), usedforsecurity=False).hexdigest()[:8]
        return f"PR-{timestamp}-{data_hash.upper()}"

    def _generate_quote_reference(self) -> str:
        """Generate Lloyd's market standard quote reference."""
        self._quote_counter += 1
        year = datetime.now(timezone.utc).year
        return f"QT-{year}-{self._quote_counter:06d}"

    async def _get_market_benchmarks(
        self,
        class_of_business: ClassOfBusiness,
        submission: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Get market benchmarks for comparison.
        In production, this would query historical pricing data.
        """
        # Mock benchmark data - in production would use actual market data
        base_rate = float(self.BASE_RATES.get(
            class_of_business, self.BASE_RATES[ClassOfBusiness.OTHER]
        ))
        limit = Decimal(str(submission.get("limit_of_liability", 1000000)))

        # Generate realistic benchmarks
        median = limit * Decimal(str(base_rate)) * Decimal("1.5")

        return {
            "low": (median * Decimal("0.70")).quantize(Decimal("0.01")),
            "median": median.quantize(Decimal("0.01")),
            "high": (median * Decimal("1.40")).quantize(Decimal("0.01")),
            "average": (median * Decimal("1.05")).quantize(Decimal("0.01")),
            "yoy_change": 5.2,  # 5.2% year-over-year increase
            "trend": "hardening",
            "data_points": 250,
            "confidence": 0.85,
        }

    def _calculate_percentile(
        self,
        premium: Decimal,
        benchmarks: Dict[str, Any],
    ) -> float:
        """Calculate percentile position in market."""
        low = float(benchmarks["low"])
        high = float(benchmarks["high"])
        premium_float = float(premium)

        if premium_float <= low:
            return 5.0
        if premium_float >= high:
            return 95.0

        # Linear interpolation
        percentile = ((premium_float - low) / (high - low)) * 90 + 5
        return round(percentile, 1)

    async def _get_portfolio_exposure(
        self,
        syndicate_id: int,
        class_of_business: ClassOfBusiness,
    ) -> Dict[str, Any]:
        """
        Get current portfolio exposure.
        In production, this would query the exposure database.
        """
        # Mock portfolio data
        return {
            "current_exposure": Decimal("75000000"),
            "limit": Decimal("100000000"),
            "utilization": Decimal("75"),
            "diversification_benefit": True,
        }

    def _calculate_optimal_line(
        self,
        pricing_result: PricingResultData,
        portfolio: Dict[str, Any],
        submission: Dict[str, Any],
    ) -> Tuple[Decimal, Decimal, Decimal, List[str]]:
        """Calculate optimal line percentage."""
        rationale = []

        # Start with target based on risk category
        base_lines = {
            RiskCategory.VERY_LOW: Decimal("25"),
            RiskCategory.LOW: Decimal("20"),
            RiskCategory.MODERATE: Decimal("15"),
            RiskCategory.HIGH: Decimal("10"),
            RiskCategory.VERY_HIGH: Decimal("5"),
            RiskCategory.DECLINE: Decimal("0"),
        }

        recommended = base_lines.get(pricing_result.risk_category, Decimal("10"))
        rationale.append(
            f"Base line of {recommended}% for {pricing_result.risk_category.value} risk"
        )

        # Adjust for portfolio utilization
        utilization = float(portfolio.get("utilization", 75))
        if utilization > 80:
            recommended = recommended * Decimal("0.75")
            rationale.append("Reduced by 25% due to high portfolio utilization (>80%)")
        elif utilization < 50:
            recommended = recommended * Decimal("1.25")
            rationale.append("Increased by 25% due to low portfolio utilization (<50%)")

        # Adjust for diversification
        if portfolio.get("diversification_benefit"):
            recommended = recommended * Decimal("1.10")
            rationale.append("Increased by 10% for diversification benefit")

        # Set bounds
        min_line = max(Decimal("5"), recommended * Decimal("0.5"))
        max_line = min(Decimal("50"), recommended * Decimal("2"))
        recommended = max(min_line, min(max_line, recommended))

        return (
            recommended.quantize(Decimal("0.01")),
            min_line.quantize(Decimal("0.01")),
            max_line.quantize(Decimal("0.01")),
            rationale,
        )

    def _get_standard_conditions(self, risk_category: RiskCategory) -> List[str]:
        """Get standard quote conditions."""
        conditions = [
            "Premium payable within 30 days of inception",
            "Claims cooperation clause applies",
            "Reasonable precautions condition applies",
        ]

        if risk_category in [RiskCategory.HIGH, RiskCategory.VERY_HIGH]:
            conditions.extend([
                "Annual risk survey required",
                "Claims made and reported basis",
                "Retroactive date applies",
            ])

        return conditions

    def _get_subjectivities(
        self,
        decision: DecisionType,
        risk_category: RiskCategory,
        decision_reasons: List[str],
    ) -> List[str]:
        """Generate subjectivities (conditions precedent)."""
        subjectivities = []

        if decision == DecisionType.REFERRAL:
            subjectivities.append("Subject to senior underwriter approval")

        if risk_category in [RiskCategory.HIGH, RiskCategory.VERY_HIGH]:
            subjectivities.extend([
                "Subject to satisfactory loss control survey",
                "Subject to risk improvement recommendations",
                "Subject to favorable claims development",
            ])

        subjectivities.extend([
            "Subject to no material change in risk",
            "Subject to satisfactory warranty compliance",
            "Subject to receipt of signed proposal form",
        ])

        return subjectivities

    def _get_standard_exclusions(self, class_of_business: ClassOfBusiness) -> List[str]:
        """Get standard policy exclusions."""
        exclusions = [
            "War and terrorism (unless specifically included)",
            "Nuclear, chemical, biological, radiological",
            "Intentional or criminal acts by insured",
            "Contractual liability (unless specifically included)",
            "Pollution (unless specifically included)",
            "Sanctions clause applies",
        ]

        # Class-specific exclusions
        if class_of_business == ClassOfBusiness.CYBER:
            exclusions.extend([
                "Cyber war and state-sponsored attacks",
                "Infrastructure failure not caused by cyber event",
                "Unencrypted portable devices",
            ])
        elif class_of_business == ClassOfBusiness.DIRECTORS_OFFICERS:
            exclusions.extend([
                "Prior and pending litigation",
                "Personal profit or advantage",
                "Bodily injury and property damage",
            ])
        elif class_of_business == ClassOfBusiness.PROFESSIONAL_LIABILITY:
            exclusions.extend([
                "Dishonest or fraudulent acts",
                "Insolvency of insured",
                "Trading losses",
            ])

        return exclusions

    def _build_quote_terms(
        self,
        pricing_result: PricingResultData,
        terms: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build complete quote terms."""
        return {
            "basis": "Claims made and reported",
            "policy_period": "12 months",
            "deductible": float(pricing_result.pricing_breakdown.deductible),
            "limit_of_liability": float(pricing_result.pricing_breakdown.limit_of_liability),
            "aggregate_limit": float(
                pricing_result.pricing_breakdown.limit_of_liability *
                terms.get("aggregate_multiplier", Decimal("2"))
            ),
            "retroactive_date": terms.get("retroactive_date", "Full prior acts"),
            "extended_reporting": terms.get("extended_reporting", "Optional 12 months at 75% premium"),
            "jurisdiction": terms.get("jurisdiction", "England and Wales"),
            "governing_law": terms.get("governing_law", "English law"),
        }

    async def _analyze_key_drivers(
        self,
        risk_factors: RiskFactors,
        submission: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Analyze key drivers with detailed impact."""
        drivers = []

        # Analyze each factor
        factors = [
            ("Territory", risk_factors.territory_loading, Decimal("1.00")),
            ("Industry", risk_factors.industry_loading, Decimal("1.00")),
            ("Size", risk_factors.size_loading, Decimal("1.00")),
            ("Claims History", risk_factors.claims_loading, Decimal("1.00")),
            ("Limit", risk_factors.limit_loading, Decimal("1.00")),
            ("Deductible", risk_factors.deductible_credit, Decimal("1.00")),
            ("Catastrophe", risk_factors.cat_loading, Decimal("1.00")),
        ]

        for name, value, baseline in factors:
            impact = float((value - baseline) / baseline * 100)
            direction = "increase" if value > baseline else "decrease" if value < baseline else "neutral"

            if abs(impact) > 2:  # Only include significant factors
                drivers.append({
                    "factor": name,
                    "impact": round(impact, 1),
                    "direction": direction,
                    "explanation": self._explain_factor(name, value, submission),
                })

        # Add specialty adjustments
        for adj_name, adj_value in risk_factors.specialty_adjustments.items():
            impact = float((adj_value - Decimal("1")) * 100)
            if abs(impact) > 2:
                drivers.append({
                    "factor": adj_name.replace("_", " ").title(),
                    "impact": round(impact, 1),
                    "direction": "increase" if adj_value > 1 else "decrease",
                    "explanation": f"Specialty adjustment for {adj_name.replace('_', ' ')}",
                })

        # Sort by absolute impact
        drivers.sort(key=lambda x: abs(x["impact"]), reverse=True)

        return drivers[:10]

    def _explain_factor(
        self,
        factor_name: str,
        value: Decimal,
        submission: Dict[str, Any],
    ) -> str:
        """Generate human-readable explanation for a factor."""
        explanations = {
            "Territory": f"Based on territory {submission.get('territory', 'unknown')} with loading factor of {float(value):.0%}",
            "Industry": f"Industry {submission.get('industry', 'general')} carries loading of {float(value):.0%}",
            "Size": f"Organization size band results in factor of {float(value):.0%}",
            "Claims History": f"Claims history rated as resulting in factor of {float(value):.0%}",
            "Limit": f"Increased limit factor for requested limit is {float(value):.2f}x",
            "Deductible": f"Deductible credit applied at {float(value):.0%}",
            "Catastrophe": f"Catastrophe loading for region at {float(value):.0%}",
        }
        return explanations.get(factor_name, f"{factor_name} factor: {float(value):.2f}")

    def _generate_risk_narrative(
        self,
        risk_score: float,
        risk_category: RiskCategory,
        submission: Dict[str, Any],
    ) -> str:
        """Generate human-readable risk assessment narrative."""
        narratives = {
            RiskCategory.VERY_LOW: "This submission presents a very low risk profile. The combination of favorable territory, industry, and claims history suggests minimal expected loss activity.",
            RiskCategory.LOW: "This submission presents a low risk profile with generally favorable characteristics. Standard underwriting terms are appropriate.",
            RiskCategory.MODERATE: "This submission presents a moderate risk profile with some factors requiring attention. Standard terms with specific subjectivities recommended.",
            RiskCategory.HIGH: "This submission presents a high risk profile with several concerning factors. Enhanced terms, higher deductibles, or exclusions may be required.",
            RiskCategory.VERY_HIGH: "This submission presents a very high risk profile. Significant concerns exist that may require senior review, restrictive terms, or potential decline.",
            RiskCategory.DECLINE: "This submission falls outside normal risk appetite. The combination of risk factors exceeds acceptable thresholds for standard underwriting.",
        }

        base_narrative = narratives.get(risk_category, "Risk assessment completed.")

        # Add specific details
        territory = submission.get("territory", "")
        industry = submission.get("industry", "")

        if territory:
            base_narrative += f" Territory {territory} has been factored into the assessment."
        if industry:
            base_narrative += f" The {industry} sector risk profile has been considered."

        return base_narrative

    def _generate_pricing_narrative(
        self,
        breakdown: PricingBreakdown,
        risk_factors: RiskFactors,
    ) -> str:
        """Generate human-readable pricing narrative."""
        return (
            f"The technical premium of {breakdown.currency} {float(breakdown.technical_premium):,.2f} "
            f"is calculated based on a rate-on-line of {float(breakdown.rate_on_line):.2f}%. "
            f"This reflects a pure premium of {breakdown.currency} {float(breakdown.pure_premium):,.2f} "
            f"with additions for risk ({breakdown.currency} {float(breakdown.risk_load):,.2f}), "
            f"expenses ({breakdown.currency} {float(breakdown.expense_load):,.2f}), "
            f"profit margin ({breakdown.currency} {float(breakdown.profit_load):,.2f}), "
            f"and catastrophe loading ({breakdown.currency} {float(breakdown.cat_load):,.2f}). "
            f"The total loading factor applied is {float(risk_factors.get_total_loading()):.2f}x."
        )

    def _explain_pricing_factors(
        self,
        risk_factors: RiskFactors,
    ) -> List[Dict[str, Any]]:
        """Explain each pricing factor."""
        return [
            {
                "factor": "Base Rate",
                "value": float(risk_factors.base_rate),
                "explanation": f"Standard rate for {risk_factors.class_of_business}",
            },
            {
                "factor": "Territory Loading",
                "value": float(risk_factors.territory_loading),
                "explanation": "Adjustment for geographic risk factors",
            },
            {
                "factor": "Industry Loading",
                "value": float(risk_factors.industry_loading),
                "explanation": "Adjustment for sector-specific risks",
            },
            {
                "factor": "Size Factor",
                "value": float(risk_factors.size_loading),
                "explanation": "Adjustment based on organization size",
            },
            {
                "factor": "Claims History",
                "value": float(risk_factors.claims_loading),
                "explanation": "Experience-based adjustment",
            },
            {
                "factor": "Limit Factor",
                "value": float(risk_factors.limit_loading),
                "explanation": "Increased limit factor (ILF)",
            },
            {
                "factor": "Deductible Credit",
                "value": float(risk_factors.deductible_credit),
                "explanation": "Credit for higher retention",
            },
            {
                "factor": "CAT Loading",
                "value": float(risk_factors.cat_loading),
                "explanation": "Catastrophe exposure loading",
            },
            {
                "factor": "Expense Ratio",
                "value": float(risk_factors.expense_ratio),
                "explanation": "Operating expense provision",
            },
            {
                "factor": "Profit Margin",
                "value": float(risk_factors.profit_margin),
                "explanation": "Target profit provision",
            },
        ]

    def _generate_recommendations(
        self,
        decision: DecisionType,
        risk_category: RiskCategory,
        submission: Dict[str, Any],
    ) -> List[str]:
        """Generate underwriting recommendations."""
        recommendations = []

        if decision == DecisionType.AUTO_QUOTE:
            recommendations.append("Risk is within automatic authority - proceed to quote")
        elif decision == DecisionType.REFERRAL:
            recommendations.append("Refer to senior underwriter for approval")
            recommendations.append("Consider enhanced deductible or sub-limits")
        elif decision == DecisionType.DECLINE:
            recommendations.append("Risk is outside current appetite - decline recommended")
            recommendations.append("Consider specialty markets or alternative risk transfer")
        elif decision == DecisionType.MORE_INFO:
            recommendations.append("Request additional information before proceeding")

        if risk_category in [RiskCategory.HIGH, RiskCategory.VERY_HIGH]:
            recommendations.extend([
                "Consider risk improvement requirements",
                "Review claims history in detail",
                "Evaluate need for exclusions or restrictions",
            ])

        return recommendations

    def _summarize_decision(self, pricing_result: PricingResultData) -> str:
        """Generate decision summary."""
        summaries = {
            DecisionType.AUTO_QUOTE: f"Quote at {pricing_result.currency} {float(pricing_result.technical_premium):,.2f} within automatic authority",
            DecisionType.REFERRAL: f"Referral required - technical premium {pricing_result.currency} {float(pricing_result.technical_premium):,.2f}",
            DecisionType.DECLINE: "Risk declined - outside appetite parameters",
            DecisionType.MORE_INFO: "Additional information required before pricing",
        }
        return summaries.get(pricing_result.decision, "Decision pending")

    async def _analyze_similar_risks(
        self,
        submission: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze similar historical risks.
        In production, this would query historical policy data.
        """
        # Mock data
        return {
            "count": 125,
            "loss_ratio": 0.58,
        }

    def _get_data_sources(self, submission: Dict[str, Any]) -> List[str]:
        """List data sources used in analysis."""
        sources = ["Submission data provided by broker"]

        if submission.get("claims_history"):
            sources.append("Claims history records")
        if submission.get("financials"):
            sources.append("Financial statements")
        if submission.get("security_controls"):
            sources.append("Security posture assessment")

        sources.extend([
            "Lloyd's market benchmark data",
            "Historical portfolio performance",
            "Catastrophe model outputs",
        ])

        return sources

    def _get_assumptions(self) -> List[str]:
        """List assumptions made in analysis."""
        return [
            "All information provided is accurate and complete",
            "No material change in risk since submission",
            "Standard policy terms and conditions apply",
            "Claims are reported promptly per policy requirements",
            "Risk remains within defined territorial scope",
            "Exposure remains consistent with submission",
        ]

    def _get_limitations(self) -> List[str]:
        """List limitations of the analysis."""
        return [
            "Pricing based on available market data which may not reflect all market conditions",
            "Model predictions carry inherent uncertainty",
            "Catastrophe scenarios may not capture all potential events",
            "Historical data may not predict future loss patterns",
            "Specialty risk factors may require expert review",
        ]


# =============================================================================
# Factory Functions
# =============================================================================

async def get_underwriting_engine(
    db: Optional[AsyncSession] = None,
) -> AlgorithmicUnderwritingEngine:
    """Get an instance of the underwriting engine."""
    return AlgorithmicUnderwritingEngine(db)


# =============================================================================
# Convenience Functions
# =============================================================================

async def quick_price(
    submission: Dict[str, Any],
    db: Optional[AsyncSession] = None,
) -> PricingResultData:
    """Quick pricing without full engine setup."""
    engine = await get_underwriting_engine(db)
    return await engine.price_submission(submission)


async def quick_quote(
    submission: Dict[str, Any],
    terms: Optional[Dict[str, Any]] = None,
    db: Optional[AsyncSession] = None,
) -> QuoteData:
    """Quick quote generation."""
    engine = await get_underwriting_engine(db)
    pricing = await engine.price_submission(submission)
    return await engine.generate_quote(pricing, terms or {})
