"""
Email Negotiation Service - AI-powered negotiation within underwriter parameters.

This module provides intelligent email negotiation capabilities:
- Analyzes broker counter-offers
- Determines optimal response strategy
- Generates negotiation emails within approved parameters
- Tracks negotiation history and outcomes
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from decimal import Decimal

logger = logging.getLogger(__name__)


class NegotiationStrategy(Enum):
    """Negotiation strategy options."""

    FIRM = "firm"  # Hold current terms
    FLEXIBLE = "flexible"  # Willing to move within limits
    COMPROMISE = "compromise"  # Split the difference
    ESCALATE = "escalate"  # Escalate to senior underwriter
    DECLINE = "decline"  # Decline to negotiate
    ACCEPT = "accept"  # Accept counter-offer as-is


class NegotiationOutcome(Enum):
    """Possible negotiation outcomes."""

    ACCEPTED = "accepted"
    COUNTERED = "countered"
    DECLINED = "declined"
    ESCALATED = "escalated"
    PENDING = "pending"


@dataclass
class NegotiationParameters:
    """Approved negotiation parameters from underwriter."""

    min_premium: Decimal  # Willing to go this low
    max_premium: Decimal  # Target/preferred
    min_deductible: Decimal  # Lowest acceptable deductible
    max_deductible: Decimal  # Preferred deductible
    min_coverage: Decimal  # Minimum coverage
    max_coverage: Decimal  # Maximum coverage
    auto_accept_threshold: Decimal  # Auto-accept if within this %
    escalation_threshold: Decimal  # Escalate if outside this %
    flexible_terms: List[str] = field(default_factory=list)
    hard_lines: List[str] = field(default_factory=list)


@dataclass
class BrokerCounterOffer:
    """Parsed counter-offer from broker."""

    premium_offered: Decimal
    deductible_offered: Decimal
    coverage_requested: Decimal
    validity_period: int  # Days
    conditions: List[str]
    concessions_requested: List[str]
    justification: str


@dataclass
class NegotiationResult:
    """Result of negotiation analysis."""

    recommended_action: NegotiationStrategy
    outcome: NegotiationOutcome
    premium_recommendation: Decimal
    deductible_recommendation: Decimal
    coverage_recommendation: Decimal
    response_strategy: str
    reasoning: List[str]
    next_steps: List[str]
    escalation_required: bool
    escalation_reason: Optional[str]
    generated_email: str
    confidence: float
    created_at: datetime


class EmailNegotiationService:
    """
    AI-powered email negotiation service.

    Analyzes broker counter-offers against approved underwriter parameters
    and determines the optimal negotiation strategy.
    """

    def __init__(self):
        self._negotiation_history: List[NegotiationResult] = []

    def analyze_counter_offer(
        self,
        counter_offer: BrokerCounterOffer,
        parameters: NegotiationParameters,
        historical_context: Optional[List[Dict]] = None,
    ) -> NegotiationResult:
        """
        Analyze a broker counter-offer and determine optimal response.

        Args:
            counter_offer: Parsed counter-offer details
            parameters: Approved negotiation parameters
            historical_context: Previous negotiations with this broker

        Returns:
            NegotiationResult with recommended action and generated email
        """
        reasoning = []
        next_steps = []

        # Analyze premium position
        premium_analysis = self._analyze_premium(
            counter_offer.premium_offered,
            parameters.min_premium,
            parameters.max_premium,
        )
        reasoning.append(
            f"Premium: Offered {counter_offer.premium_offered}, Target {parameters.max_premium}"
        )

        # Analyze deductible position
        deductible_analysis = self._analyze_deductible(
            counter_offer.deductible_offered,
            parameters.min_deductible,
            parameters.max_deductible,
        )
        reasoning.append(
            f"Deductible: Offered {counter_offer.deductible_offered}, Range {parameters.min_deductible}-{parameters.max_deductible}"
        )

        # Analyze coverage
        coverage_analysis = self._analyze_coverage(
            counter_offer.coverage_requested,
            parameters.min_coverage,
            parameters.max_coverage,
        )
        reasoning.append(
            f"Coverage: Requested {counter_offer.coverage_requested}, Range {parameters.min_coverage}-{parameters.max_coverage}"
        )

        # Determine overall negotiation position
        position_score = self._calculate_position_score(
            premium_analysis, deductible_analysis, coverage_analysis
        )
        reasoning.append(f"Overall position score: {position_score:.2%}")

        # Determine strategy based on position
        strategy, outcome, escalation = self._determine_strategy(
            position_score,
            premium_analysis,
            deductible_analysis,
            coverage_analysis,
            parameters,
        )

        # Generate recommendations
        premium_rec, deductible_rec, coverage_rec = self._generate_recommendations(
            strategy,
            counter_offer,
            parameters,
            premium_analysis,
            deductible_analysis,
            coverage_analysis,
        )

        # Build response strategy description
        response_strategy = self._build_response_strategy(
            strategy,
            counter_offer,
            premium_rec,
            deductible_rec,
            coverage_rec,
            parameters,
        )

        # Generate negotiation email
        generated_email = self._generate_response_email(
            counter_offer,
            strategy,
            premium_rec,
            deductible_rec,
            coverage_rec,
            parameters,
        )

        # Determine next steps
        next_steps = self._determine_next_steps(
            strategy, outcome, counter_offer.validity_period
        )

        return NegotiationResult(
            recommended_action=strategy,
            outcome=outcome,
            premium_recommendation=premium_rec,
            deductible_recommendation=deductible_rec,
            coverage_recommendation=coverage_rec,
            response_strategy=response_strategy,
            reasoning=reasoning,
            next_steps=next_steps,
            escalation_required=escalation["required"],
            escalation_reason=escalation["reason"],
            generated_email=generated_email,
            confidence=self._calculate_confidence(position_score, strategy),
            created_at=datetime.now(),
        )

    def _analyze_premium(
        self, offered: Decimal, minimum: Decimal, target: Decimal
    ) -> Dict:
        """Analyze premium position against parameters."""
        target_pct = (offered / target * 100) if target > 0 else 0
        min_pct = (offered / minimum * 100) if minimum > 0 else 0

        if offered >= target:
            return {
                "position": "excellent",
                "pct_of_target": target_pct,
                "above_minimum": min_pct,
                "action": "accept",
            }
        elif offered >= minimum:
            return {
                "position": "acceptable",
                "pct_of_target": target_pct,
                "above_minimum": min_pct,
                "action": "negotiate",
            }
        else:
            return {
                "position": "unacceptable",
                "pct_of_target": target_pct,
                "above_minimum": min_pct,
                "action": "decline",
            }

    def _analyze_deductible(
        self, offered: Decimal, minimum: Decimal, maximum: Decimal
    ) -> Dict:
        """Analyze deductible position against parameters."""
        if offered <= maximum and offered >= minimum:
            return {"position": "acceptable", "within_range": True, "action": "accept"}
        elif offered > maximum:
            return {
                "position": "too_high",
                "within_range": False,
                "action": "negotiate",
            }
        else:
            return {
                "position": "too_low",
                "within_range": False,
                "action": "accept_with_caution",
            }

    def _analyze_coverage(
        self, requested: Decimal, minimum: Decimal, maximum: Decimal
    ) -> Dict:
        """Analyze coverage position against parameters."""
        if requested <= maximum and requested >= minimum:
            return {"position": "acceptable", "within_range": True, "action": "accept"}
        elif requested > maximum:
            return {
                "position": "excessive",
                "within_range": False,
                "action": "negotiate",
            }
        else:
            return {"position": "cautious", "within_range": True, "action": "accept"}

    def _calculate_position_score(
        self, premium: Dict, deductible: Dict, coverage: Dict
    ) -> float:
        """Calculate overall negotiation position score."""
        weights = {"premium": 0.5, "deductible": 0.3, "coverage": 0.2}

        score = 0.0
        position_map = {
            "excellent": 1.0,
            "acceptable": 0.7,
            "too_high": 0.4,
            "too_low": 0.6,
            "excessive": 0.3,
            "cautious": 0.8,
        }

        score += (
            position_map.get(premium.get("position", "acceptable"), 0.5)
            * weights["premium"]
        )
        score += (
            position_map.get(deductible.get("position", "acceptable"), 0.5)
            * weights["deductible"]
        )
        score += (
            position_map.get(coverage.get("position", "acceptable"), 0.5)
            * weights["coverage"]
        )

        return score

    def _determine_strategy(
        self,
        position_score: float,
        premium: Dict,
        deductible: Dict,
        coverage: Dict,
        parameters: NegotiationParameters,
    ) -> Tuple[NegotiationStrategy, NegotiationOutcome, Dict]:
        """Determine negotiation strategy and outcome."""
        escalation = {"required": False, "reason": None}

        # Check for auto-accept
        if position_score >= 0.95 and premium["action"] == "accept":
            return NegotiationStrategy.FIRM, NegotiationOutcome.ACCEPTED, escalation

        # Check for decline
        if premium["action"] == "decline":
            return NegotiationStrategy.DECLINE, NegotiationOutcome.DECLINED, escalation

        # Check for auto-accept threshold
        if position_score >= (100 - float(parameters.auto_accept_threshold)) / 100:
            return NegotiationStrategy.FLEXIBLE, NegotiationOutcome.ACCEPTED, escalation

        # Check for escalation threshold
        if position_score < (100 - float(parameters.escalation_threshold)) / 100:
            escalation["required"] = True
            escalation["reason"] = (
                f"Position score {position_score:.1%} below escalation threshold"
            )
            return (
                NegotiationStrategy.ESCALATE,
                NegotiationOutcome.ESCALATED,
                escalation,
            )

        # Default to negotiate
        if position_score >= 0.7:
            return (
                NegotiationStrategy.COMPROMISE,
                NegotiationOutcome.COUNTERED,
                escalation,
            )
        else:
            return (
                NegotiationStrategy.FLEXIBLE,
                NegotiationOutcome.COUNTERED,
                escalation,
            )

    def _generate_recommendations(
        self,
        strategy: NegotiationStrategy,
        counter_offer: BrokerCounterOffer,
        parameters: NegotiationParameters,
        premium: Dict,
        deductible: Dict,
        coverage: Dict,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """Generate premium, deductible, coverage recommendations."""
        if strategy in [NegotiationStrategy.FIRM, NegotiationStrategy.DECLINE]:
            return (
                counter_offer.premium_offered,
                counter_offer.deductible_offered,
                counter_offer.coverage_requested,
            )

        if strategy == NegotiationStrategy.ACCEPT:
            return (
                counter_offer.premium_offered,
                counter_offer.deductible_offered,
                counter_offer.coverage_requested,
            )

        # Calculate compromise position
        if strategy == NegotiationStrategy.COMPROMISE:
            premium_rec = (counter_offer.premium_offered + parameters.max_premium) / 2
            deductible_rec = (
                counter_offer.deductible_offered + parameters.max_deductible
            ) / 2
            coverage_rec = min(
                counter_offer.coverage_requested, parameters.max_coverage
            )
        else:  # FLEXIBLE
            premium_rec = max(counter_offer.premium_offered, parameters.min_premium)
            deductible_rec = min(
                max(counter_offer.deductible_offered, parameters.min_deductible),
                parameters.max_deductible,
            )
            coverage_rec = min(
                counter_offer.coverage_requested, parameters.max_coverage
            )

        return premium_rec, deductible_rec, coverage_rec

    def _build_response_strategy(
        self,
        strategy: NegotiationStrategy,
        counter_offer: BrokerCounterOffer,
        premium: Decimal,
        deductible: Decimal,
        coverage: Decimal,
        parameters: NegotiationParameters,
    ) -> str:
        """Build human-readable response strategy description."""
        strategies = {
            NegotiationStrategy.FIRM: f"Hold firm at current terms. Premium: £{premium:,.0f}",
            NegotiationStrategy.FLEXIBLE: f"Flexible approach - willing to move within parameters. Premium: £{premium:,.0f}",
            NegotiationStrategy.COMPROMISE: f"Seek middle ground. Proposing £{premium:,.0f} premium, £{deductible:,.0f} deductible",
            NegotiationStrategy.ESCALATE: "Escalate to senior underwriter - position below thresholds",
            NegotiationStrategy.DECLINE: "Decline to negotiate - terms outside acceptable parameters",
        }
        return strategies.get(strategy, "Unknown strategy")

    def _generate_response_email(
        self,
        counter_offer: BrokerCounterOffer,
        strategy: NegotiationStrategy,
        premium: Decimal,
        deductible: Decimal,
        coverage: Decimal,
        parameters: NegotiationParameters,
    ) -> str:
        """Generate negotiation response email."""

        templates = {
            NegotiationStrategy.ACCEPT: f"""
Dear {counter_offer.conditions},

Thank you for your counter-offer. We are pleased to accept the revised terms:

Premium: £{premium:,.0f}
Deductible: £{deductible:,.0f}
Coverage: £{coverage:,.0f}

Please bind within {counter_offer.validity_period} days.

Best regards,
InstantRisk Underwriting Team
""",
            NegotiationStrategy.COMPROMISE: f"""
Dear {counter_offer.conditions},

Thank you for your counter-offer. We've reviewed carefully and would like to find a mutually acceptable solution.

After careful consideration, we can offer:

Premium: £{premium:,.0f} (representing a competitive rate)
Deductible: £{deductible:,.0f}
Coverage: £{coverage:,.0f}

We believe this represents a fair compromise that provides excellent value while maintaining the coverage you require.

Please let us know if these terms are acceptable, or if you'd like to discuss further.

Best regards,
InstantRisk Underwriting Team
""",
            NegotiationStrategy.FLEXIBLE: f"""
Dear {counter_offer.conditions},

Thank you for the counter-offer. We're committed to finding a solution that works for both parties.

We've analyzed your proposal and can confirm we're able to be flexible on certain terms:

Premium: £{premium:,.0f}
Deductible: £{deductible:,.0f}  
Coverage: £{coverage:,.0f}

We're happy to discuss any adjustments needed within our underwriting guidelines. Please let us know how you'd like to proceed.

Best regards,
InstantRisk Underwriting Team
""",
            NegotiationStrategy.ESCALATE: f"""
Dear {counter_offer.conditions},

Thank you for your counter-offer. We appreciate the time you've put into this submission.

Your proposal has been forwarded to our Senior Underwriting Team for review given the complexity and specific terms requested. They will provide a comprehensive response within 24-48 hours.

We remain committed to finding a solution and will be in touch shortly with an update.

Best regards,
InstantRisk Underwriting Team
""",
            NegotiationStrategy.DECLINE: f"""
Dear {counter_offer.conditions},

Thank you for your submission and counter-offer. We've given it careful consideration.

Unfortunately, we're unable to proceed with the terms proposed as they fall outside our underwriting guidelines and risk parameters.

We would welcome the opportunity to discuss alternative options or review a revised submission that aligns more closely with our appetite.

Best regards,
InstantRisk Underwriting Team
""",
        }

        return templates.get(strategy, "Please contact us to discuss.")

    def _determine_next_steps(
        self,
        strategy: NegotiationStrategy,
        outcome: NegotiationOutcome,
        validity_period: int,
    ) -> List[str]:
        """Determine next steps based on negotiation result."""
        steps = []

        if outcome == NegotiationOutcome.ACCEPTED:
            steps = [
                f"Generate formal acceptance documentation",
                f"Request broker to bind within {validity_period} days",
                f"Update assessment status to 'Bound'",
                f"Log negotiation outcome",
            ]
        elif outcome == NegotiationOutcome.COUNTERED:
            steps = [
                f"Send counter-offer email to broker",
                f"Update assessment with proposed terms",
                f"Set reminder to follow up in 48 hours",
                f"Log negotiation for tracking",
            ]
        elif outcome == NegotiationOutcome.ESCALATED:
            steps = [
                f"Notify senior underwriter of escalation",
                f"Provide full context and analysis",
                f"Schedule review meeting within 24 hours",
                f"Inform broker of extended timeline",
            ]
        elif outcome == NegotiationOutcome.DECLINED:
            steps = [
                f"Send polite decline email",
                f"Update assessment status to 'Declined'",
                f"Log reason for decline",
                f"Offer alternative options if applicable",
            ]

        return steps

    def _calculate_confidence(
        self, position_score: float, strategy: NegotiationStrategy
    ) -> float:
        """Calculate confidence score for the negotiation result."""
        base_confidence = position_score

        # Adjust for strategy complexity
        if strategy in [NegotiationStrategy.FIRM, NegotiationStrategy.DECLINE]:
            multiplier = 1.0
        elif strategy in [NegotiationStrategy.ACCEPT, NegotiationStrategy.COMPROMISE]:
            multiplier = 0.95
        else:  # ESCALATE, FLEXIBLE
            multiplier = 0.85

        return min(base_confidence * multiplier, 1.0)

    def get_negotiation_templates(self) -> Dict:
        """Return available negotiation email templates."""
        return {
            "accept": "Standard acceptance email - hold firm on accepted terms",
            "counter": "Counter-offer email - propose revised terms",
            "flexible": "Flexible approach email - open to discussion",
            "escalate": "Escalation email - senior underwriter review",
            "decline": "Polite decline email - offer alternatives",
        }

    def validate_parameters(
        self, parameters: NegotiationParameters
    ) -> Tuple[bool, List[str]]:
        """Validate negotiation parameters are logical."""
        errors = []

        if parameters.min_premium > parameters.max_premium:
            errors.append("Minimum premium cannot exceed maximum premium")

        if parameters.min_deductible > parameters.max_deductible:
            errors.append("Minimum deductible cannot exceed maximum deductible")

        if parameters.min_coverage > parameters.max_coverage:
            errors.append("Minimum coverage cannot exceed maximum coverage")

        if parameters.auto_accept_threshold > parameters.escalation_threshold:
            errors.append(
                "Auto-accept threshold must be less than escalation threshold"
            )

        if (
            parameters.auto_accept_threshold < 0
            or parameters.auto_accept_threshold > 50
        ):
            errors.append("Auto-accept threshold must be between 0-50%")

        return len(errors) == 0, errors


# Singleton instance
email_negotiation_service = EmailNegotiationService()
