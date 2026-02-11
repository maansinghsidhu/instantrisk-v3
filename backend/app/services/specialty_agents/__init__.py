"""
InstantRisk V3 - Specialty Lines AI Agents

Domain-specific AI agents for complex insurance classes.
Each agent has specialized knowledge for underwriting particular risk types.

Addresses Gap 4: Specialty Lines Complexity
"""

from app.services.specialty_agents.cyber_agent import CyberUnderwritingAgent
from app.services.specialty_agents.marine_agent import MarineCargoAgent
from app.services.specialty_agents.political_risk_agent import PoliticalRiskAgent
from app.services.specialty_agents.do_agent import DOUnderwritingAgent

__all__ = [
    "CyberUnderwritingAgent",
    "MarineCargoAgent",
    "PoliticalRiskAgent",
    "DOUnderwritingAgent",
]
