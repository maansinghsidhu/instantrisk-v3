"""
InstantRisk V2 - Feature Limits Configuration

This module defines the feature limits and access controls for each subscription tier.

Tier Features:
- TRIAL: Just GO/NO-GO decision, nothing else
- BASIC: GO/NO-GO + Confidence + UW% + Sum Insured + Decision (NO ClaimSense, NO Docs)
- PREMIUM: All features
"""

from app.models.subscription import SubscriptionTier


# Feature limits and access controls by subscription tier
TIER_LIMITS = {
    SubscriptionTier.TRIAL: {
        "monthly_assessments": 5,
        "monthly_documents": 0,
        "monthly_chat_messages": 0,
        "storage_gb": 0.5,
        "analysis_modes": ["quick"],
        "features": {
            # Core features - Trial gets ONLY GO/NO-GO decision
            "go_no_go_decision": True,      # Just GO or NO-GO, nothing else
            "confidence_score": False,
            "underwriting_percentage": False,
            "sum_insured": False,
            "underwriter_decision": False,
            "risk_analysis": False,
            # Premium features - NOT available to Trial
            "claimsense_chat": False,
            "document_generation": False,
            "deep_analysis": False,
            "sanctions_screening": False,
            "advanced_analytics": False,
            # Sharing - available to all
            "shareable_link": True,
            # Analysis modes
            "quick_analysis": True,
            "go_no_go_analysis": False,
        }
    },
    SubscriptionTier.BASIC: {
        "monthly_assessments": 25,
        "monthly_documents": 0,
        "monthly_chat_messages": 0,
        "storage_gb": 2,
        "analysis_modes": ["quick", "go_no_go"],
        "features": {
            # Core features - Basic gets GO/NO-GO + details
            "go_no_go_decision": True,
            "confidence_score": True,         # YES
            "underwriting_percentage": True,  # YES
            "sum_insured": True,              # YES
            "underwriter_decision": True,     # YES
            "risk_analysis": False,           # NO rationale for Basic
            # Premium features - NOT available to Basic
            "claimsense_chat": False,         # NO
            "document_generation": False,     # NO
            "deep_analysis": False,
            "sanctions_screening": False,
            "advanced_analytics": False,
            # Sharing - available to all
            "shareable_link": True,
            # Analysis modes
            "quick_analysis": True,
            "go_no_go_analysis": True,
        }
    },
    SubscriptionTier.PREMIUM: {
        "monthly_assessments": 100,
        "monthly_documents": 50,
        "monthly_chat_messages": 500,
        "storage_gb": 10,
        "analysis_modes": ["quick", "go_no_go", "deep"],
        "features": {
            # Core features - Premium gets everything
            "go_no_go_decision": True,
            "confidence_score": True,
            "underwriting_percentage": True,
            "sum_insured": True,
            "underwriter_decision": True,
            "risk_analysis": True,            # Full rationale
            # Premium features - all available
            "claimsense_chat": True,
            "document_generation": True,
            "deep_analysis": True,
            "sanctions_screening": True,
            "advanced_analytics": True,
            # Sharing - available to all
            "shareable_link": True,
            # Analysis modes
            "quick_analysis": True,
            "go_no_go_analysis": True,
        }
    },
}


def get_tier_limits(tier: SubscriptionTier) -> dict:
    """Get the limits configuration for a subscription tier."""
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.TRIAL])


def get_feature_access(tier: SubscriptionTier, feature_name: str) -> bool:
    """Check if a tier has access to a specific feature."""
    tier_config = get_tier_limits(tier)
    return tier_config.get("features", {}).get(feature_name, False)


def get_limit_value(tier: SubscriptionTier, limit_name: str) -> int:
    """Get the limit value for a specific resource."""
    tier_config = get_tier_limits(tier)
    return tier_config.get(limit_name, 0)


def get_allowed_analysis_modes(tier: SubscriptionTier) -> list:
    """Get the list of analysis modes allowed for a tier."""
    tier_config = get_tier_limits(tier)
    return tier_config.get("analysis_modes", [])


# Feature descriptions for UI display
FEATURE_DESCRIPTIONS = {
    "go_no_go_decision": {
        "name": "GO/NO-GO Decision",
        "description": "Get clear accept/reject recommendations with visual indicators",
        "icon": "traffic_light"
    },
    "confidence_score": {
        "name": "Confidence Score",
        "description": "AI confidence percentage for the decision",
        "icon": "speed"
    },
    "underwriting_percentage": {
        "name": "Underwriting Percentage",
        "description": "Recommended syndicate underwriting percentage",
        "icon": "percent"
    },
    "sum_insured": {
        "name": "Sum Insured",
        "description": "Recommended sum to be insured",
        "icon": "attach_money"
    },
    "underwriter_decision": {
        "name": "Underwriter Decision",
        "description": "Final underwriter decision recommendation",
        "icon": "gavel"
    },
    "risk_analysis": {
        "name": "Risk Analysis",
        "description": "Detailed analysis explaining the decision rationale",
        "icon": "analytics"
    },
    "claimsense_chat": {
        "name": "ClaimSense Chat",
        "description": "AI-powered chat to ask questions and fine-tune decisions",
        "icon": "chat"
    },
    "document_generation": {
        "name": "Document Generation",
        "description": "Generate professional insurance documents automatically",
        "icon": "description"
    },
    "deep_analysis": {
        "name": "Deep Analysis",
        "description": "Comprehensive multi-agent analysis for complex risks",
        "icon": "psychology"
    },
    "advanced_analytics": {
        "name": "Advanced Analytics",
        "description": "Detailed charts, trends, and portfolio insights",
        "icon": "insights"
    },
    "sanctions_screening": {
        "name": "Sanctions Screening",
        "description": "Screen entities against global sanctions lists (OFAC, UN, EU, etc.)",
        "icon": "security"
    },
    "shareable_link": {
        "name": "Shareable Link",
        "description": "Create temporary 24-hour links to share analysis with partners",
        "icon": "share"
    },
}
