"""
InstantRisk V3 - Marine Cargo Underwriting Agent

Specialized AI agent for marine cargo risk assessment.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional


@dataclass
class VoyageRisk:
    """Risk assessment for a voyage."""
    risk_score: float
    route_risk: str
    seasonal_factor: float
    piracy_exposure: bool
    war_risk_territory: bool


@dataclass
class CargoRisk:
    """Risk assessment for cargo type."""
    susceptibility_score: float
    theft_risk: str
    damage_risk: str
    recommended_clauses: List[str]


class MarineCargoAgent:
    """AI agent for marine cargo underwriting."""

    # High-risk shipping routes
    HIGH_RISK_ROUTES = [
        "Gulf of Aden", "Strait of Malacca", "West Africa",
        "South China Sea", "Caribbean", "Bangladesh Coast"
    ]

    # War risk territories
    WAR_RISK_TERRITORIES = [
        "Ukraine", "Russia", "Yemen", "Syria", "Libya",
        "Venezuela", "Iran", "North Korea"
    ]

    # Institute Cargo Clauses
    CARGO_CLAUSES = {
        "ICC_A": "All Risks - widest cover",
        "ICC_B": "Named perils - intermediate cover",
        "ICC_C": "Named perils - basic cover",
        "WAR": "War, strikes, terrorism",
        "THEFT": "Theft, pilferage and non-delivery",
        "REEFER": "Refrigerated cargo breakdown",
    }

    async def calculate_voyage_risk(self, route: Dict[str, Any]) -> VoyageRisk:
        """Calculate risk for a specific voyage route."""
        origin = route.get('origin', '')
        destination = route.get('destination', '')
        transit_points = route.get('transit_points', [])

        # Check route risk factors
        all_points = [origin, destination] + transit_points
        piracy_exposure = any(p in self.HIGH_RISK_ROUTES for p in all_points)
        war_territory = any(p in self.WAR_RISK_TERRITORIES for p in all_points)

        # Calculate base risk
        base_score = 30
        if piracy_exposure:
            base_score += 25
        if war_territory:
            base_score += 30

        # Seasonal factor
        month = route.get('month', 6)
        seasonal = 1.0
        if month in [11, 12, 1, 2]:  # Winter - higher risk
            seasonal = 1.2
        elif month in [6, 7, 8]:  # Hurricane season
            seasonal = 1.15

        return VoyageRisk(
            risk_score=min(100, base_score * seasonal),
            route_risk="high" if base_score > 50 else "moderate" if base_score > 30 else "low",
            seasonal_factor=seasonal,
            piracy_exposure=piracy_exposure,
            war_risk_territory=war_territory,
        )

    async def assess_cargo_susceptibility(self, cargo_type: str) -> CargoRisk:
        """Assess cargo type for damage/theft susceptibility."""
        # Cargo susceptibility profiles
        profiles = {
            'electronics': {'theft': 'high', 'damage': 'high', 'clauses': ['ICC_A', 'THEFT']},
            'machinery': {'theft': 'medium', 'damage': 'medium', 'clauses': ['ICC_A']},
            'textiles': {'theft': 'medium', 'damage': 'low', 'clauses': ['ICC_B']},
            'food': {'theft': 'low', 'damage': 'high', 'clauses': ['ICC_A', 'REEFER']},
            'chemicals': {'theft': 'low', 'damage': 'high', 'clauses': ['ICC_A']},
            'vehicles': {'theft': 'high', 'damage': 'medium', 'clauses': ['ICC_A', 'THEFT']},
            'bulk': {'theft': 'low', 'damage': 'low', 'clauses': ['ICC_C']},
        }

        profile = profiles.get(cargo_type.lower(), profiles['bulk'])
        theft_scores = {'low': 0.2, 'medium': 0.5, 'high': 0.8}
        damage_scores = {'low': 0.2, 'medium': 0.5, 'high': 0.8}

        return CargoRisk(
            susceptibility_score=(theft_scores[profile['theft']] + damage_scores[profile['damage']]) / 2 * 100,
            theft_risk=profile['theft'],
            damage_risk=profile['damage'],
            recommended_clauses=profile['clauses'],
        )

    async def recommend_clauses(self, submission: Dict[str, Any]) -> List[Dict[str, str]]:
        """Recommend appropriate cargo clauses."""
        cargo_type = submission.get('cargo_type', 'general')
        route = submission.get('route', {})

        cargo_risk = await self.assess_cargo_susceptibility(cargo_type)
        voyage_risk = await self.calculate_voyage_risk(route)

        clauses = []
        for clause_code in cargo_risk.recommended_clauses:
            clauses.append({
                'code': clause_code,
                'description': self.CARGO_CLAUSES.get(clause_code, ''),
                'required': True,
            })

        # Add war clause if war territory
        if voyage_risk.war_risk_territory:
            clauses.append({
                'code': 'WAR',
                'description': self.CARGO_CLAUSES['WAR'],
                'required': True,
            })

        return clauses
