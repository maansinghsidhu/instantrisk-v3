"""
Scenario Simulation Service - Monte Carlo risk modeling.

Provides what-if analysis for underwriters to model different scenarios.
"""

from typing import Dict, List, Optional
from decimal import Decimal
import random
import statistics


class ScenarioSimulationService:
    def run_monte_carlo(
        self,
        premium: Decimal,
        loss_ratio: float,
        exposure_count: int,
        iterations: int = 10000,
    ) -> Dict:
        losses = []
        premium_f = float(premium)
        for _ in range(iterations):
            simulated_loss_ratio = max(0, random.gauss(loss_ratio, loss_ratio * 0.3))
            loss_amount = premium_f * simulated_loss_ratio
            losses.append(loss_amount)

        losses.sort()
        return {
            "premium": premium_f,
            "expected_loss": premium_f * loss_ratio,
            "var_95": losses[int(iterations * 0.95)],
            "var_99": losses[int(iterations * 0.99)],
            "mean": sum(losses) / len(losses),
            "std_dev": statistics.stdev(losses) if len(losses) > 1 else 0,
            "percentiles": {
                "50": losses[int(iterations * 0.50)],
                "75": losses[int(iterations * 0.75)],
                "90": losses[int(iterations * 0.90)],
                "95": losses[int(iterations * 0.95)],
            },
        }

    def calculate_impact(self, base_scenario: Dict, changes: List[Dict]) -> Dict:
        impact_results = []
        for change in changes:
            factor = change.get("factor", 1.0)
            new_premium = base_scenario["premium"] * factor
            new_loss = base_scenario["expected_loss"] * factor
            impact_results.append(
                {
                    "change": change.get("description", "Unknown"),
                    "new_premium": new_premium,
                    "new_expected_loss": new_loss,
                    "combined_ratio": new_loss / new_premium if new_premium > 0 else 0,
                }
            )
        return {"impacts": impact_results}


scenario_service = ScenarioSimulationService()
