"""
AutoGen-based Document Processor for Insurance Documents
5-Agent Multi-Agent System with Progress Tracking
Uses Microsoft AutoGen patterns with AWS Bedrock Claude

Agents:
1. DocumentClassifier - Identifies document type and validates
2. DataExtractor - Extracts all insurance data fields
3. RiskAnalyst - Analyzes risk factors and exposures
4. Underwriter - Makes GO/NO-GO decision (GO if confidence >= 60%)
5. QualityAssurance - Final validation and quality check

Analysis Modes:
- QUICK: 2 agents (Classifier + Underwriter) ~15s
- GO_NO_GO: 3 agents (Classifier + Extractor + Underwriter) ~30s
- DEEP: 5 agents (full pipeline) ~60s
"""

import os
import json
import httpx
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv

if TYPE_CHECKING:
    from app.services.autogen_tools import AutoGenToolExecutor

load_dotenv()

# Configure logging to ensure output is visible
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AnalysisMode(str, Enum):
    """Analysis mode determining which agents run."""
    QUICK = "quick"         # Fast decision: Classifier + Underwriter
    GO_NO_GO = "go_no_go"   # Standard: Classifier + Extractor + Underwriter
    DEEP = "deep"           # Comprehensive: All 5 agents


# Time estimates per agent (seconds) - base time for ~2000 chars of document
# Updated based on actual MiniMax API response times
AGENT_TIME_ESTIMATES = {
    "DocumentClassifier": 15,
    "DataExtractor": 25,
    "RiskAnalyst": 30,
    "FinancialAnalyst": 25,
    "ComplianceAgent": 25,
    "ExposureAnalyst": 25,
    "Underwriter": 30,
    "VerificationAgent": 20,
    "QualityAssurance": 20
}

# Agents used per mode - More agents = higher confidence
MODE_AGENTS = {
    AnalysisMode.QUICK: ["DocumentClassifier", "Underwriter"],
    AnalysisMode.GO_NO_GO: ["DocumentClassifier", "DataExtractor", "RiskAnalyst", "Underwriter"],
    AnalysisMode.DEEP: ["DocumentClassifier", "DataExtractor", "FinancialAnalyst", "RiskAnalyst",
                        "ComplianceAgent", "ExposureAnalyst", "Underwriter", "VerificationAgent", "QualityAssurance"]
}

# Mode descriptions for UI
MODE_DESCRIPTIONS = {
    AnalysisMode.QUICK: {
        "name": "Quick Analysis",
        "description": "Fast classification and decision. Best for time-sensitive quotes.",
        "agents": ["Classifier", "Underwriter"],
        "icon": "flash_on"
    },
    AnalysisMode.GO_NO_GO: {
        "name": "Go/No-Go Analysis",
        "description": "Standard 4-agent analysis with risk assessment. Recommended for most submissions.",
        "agents": ["Classifier", "Extractor", "Risk Analyst", "Underwriter"],
        "icon": "gavel"
    },
    AnalysisMode.DEEP: {
        "name": "Deep Analysis",
        "description": "Comprehensive 9-agent analysis with financial, compliance, and verification. Best for complex or large risks.",
        "agents": ["Classifier", "Extractor", "Financial", "Risk Analyst", "Compliance", "Exposure", "Underwriter", "Verification", "QA"],
        "icon": "analytics"
    }
}

# Detailed sub-steps for each agent (for live progress commentary)
AGENT_DETAILED_STEPS = {
    "DocumentClassifier": [
        {"step": "reading", "desc": "Reading uploaded documents..."},
        {"step": "ocr", "desc": "Extracting text from images/PDFs..."},
        {"step": "classifying", "desc": "Identifying document types..."},
        {"step": "validating", "desc": "Validating document structure..."},
    ],
    "DataExtractor": [
        {"step": "parsing", "desc": "Parsing document content..."},
        {"step": "extracting_parties", "desc": "Extracting insured & broker names..."},
        {"step": "extracting_coverage", "desc": "Extracting coverage details..."},
        {"step": "extracting_financials", "desc": "Extracting premium & limits..."},
        {"step": "extracting_dates", "desc": "Extracting policy dates..."},
        {"step": "extracting_territory", "desc": "Identifying territory & jurisdiction..."},
    ],
    "RiskAnalyst": [
        {"step": "analyzing_exposure", "desc": "Analyzing exposure profile..."},
        {"step": "nat_cat_check", "desc": "Checking natural catastrophe exposure..."},
        {"step": "checking_aggregation", "desc": "Checking aggregation risk..."},
        {"step": "scoring_risk", "desc": "Calculating risk score..."},
        {"step": "identifying_concerns", "desc": "Identifying risk concerns..."},
    ],
    "Underwriter": [
        {"step": "reviewing_data", "desc": "Reviewing extracted data..."},
        {"step": "checking_appetite", "desc": "Checking underwriting appetite..."},
        {"step": "assessing_pricing", "desc": "Assessing premium adequacy..."},
        {"step": "applying_rules", "desc": "Applying underwriting rules..."},
        {"step": "making_decision", "desc": "Making GO/NO-GO decision..."},
        {"step": "writing_rationale", "desc": "Writing decision rationale..."},
    ],
    "QualityAssurance": [
        {"step": "checking_data", "desc": "Checking data completeness..."},
        {"step": "verifying_analysis", "desc": "Verifying analysis quality..."},
        {"step": "compliance_check", "desc": "Running compliance checks..."},
        {"step": "final_validation", "desc": "Final validation & sign-off..."},
    ],
}


def estimate_analysis_time(
    mode: AnalysisMode,
    document_count: int = 1,
    total_chars: int = 2000
) -> Dict[str, Any]:
    """
    Estimate processing time for given analysis mode and documents.

    Args:
        mode: Analysis mode (QUICK, GO_NO_GO, DEEP)
        document_count: Number of documents to process
        total_chars: Total character count across all documents

    Returns:
        Dictionary with time estimates and breakdown
    """
    agents = MODE_AGENTS.get(mode, MODE_AGENTS[AnalysisMode.DEEP])

    # Base time for each agent
    breakdown = []
    total_seconds = 0

    # Document complexity multiplier based on character count
    char_multiplier = max(1.0, total_chars / 2000)  # Scale up for longer docs
    doc_multiplier = max(1.0, document_count * 0.7)  # Additional docs add ~70% each

    for agent in agents:
        base_time = AGENT_TIME_ESTIMATES.get(agent, 10)
        adjusted_time = int(base_time * char_multiplier * doc_multiplier)
        breakdown.append({
            "agent": agent,
            "estimated_seconds": adjusted_time
        })
        total_seconds += adjusted_time

    return {
        "mode": mode.value,
        "mode_info": MODE_DESCRIPTIONS.get(mode, {}),
        "document_count": document_count,
        "estimated_seconds": total_seconds,
        "estimated_range": {
            "min_seconds": int(total_seconds * 0.7),
            "max_seconds": int(total_seconds * 1.5)
        },
        "breakdown": breakdown,
        "agents_count": len(agents)
    }


def get_all_mode_estimates(document_count: int = 1, total_chars: int = 2000) -> List[Dict]:
    """Get time estimates for all analysis modes."""
    return [
        estimate_analysis_time(mode, document_count, total_chars)
        for mode in AnalysisMode
    ]


from app.services.bedrock_client import BedrockClient as _BedrockClientClass

# Model IDs for agent selection (Haiku for simple tasks, Sonnet for reasoning)
BEDROCK_MODEL_SONNET = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
BEDROCK_MODEL_HAIKU = os.getenv("BEDROCK_FALLBACK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")

# Agent to model mapping - use cheap Haiku for simple agents, Sonnet for reasoning
AGENT_MODEL_MAP = {
    "DocumentClassifier": BEDROCK_MODEL_HAIKU,  # Simple classification
    "DataExtractor": BEDROCK_MODEL_HAIKU,       # Structured extraction
    "FinancialAnalyst": BEDROCK_MODEL_HAIKU,    # Financial metrics
    "ComplianceAgent": BEDROCK_MODEL_HAIKU,     # Compliance checks
    "VerificationAgent": BEDROCK_MODEL_HAIKU,   # Data verification
    "QualityAssurance": BEDROCK_MODEL_HAIKU,    # QA validation
    "RiskAnalyst": BEDROCK_MODEL_SONNET,        # Needs reasoning
    "ExposureAnalyst": BEDROCK_MODEL_SONNET,    # Needs reasoning
    "Underwriter": BEDROCK_MODEL_SONNET,        # Critical decision making
}


class AgentProgress:
    """Track and report agent processing progress with detailed sub-steps."""

    def __init__(self):
        self.steps: List[Dict] = []
        self.current_agent: str = ""
        self.start_time: datetime = None
        self.current_step_index: int = 0
        self.current_sub_step: str = ""
        self.live_findings: List[Dict] = []

    def start(self, agent_name: str, description: str):
        self.current_agent = agent_name
        self.start_time = datetime.now()
        self.current_step_index = 0
        self.steps.append({
            "agent": agent_name,
            "status": "running",
            "description": description,
            "started_at": self.start_time.isoformat(),
            "completed_at": None,
            "duration_ms": None,
            "output_preview": None,
            "sub_steps": AGENT_DETAILED_STEPS.get(agent_name, []),
            "current_sub_step": 0
        })

    def update_sub_step(self, step_index: int, description: str = None):
        """Update current sub-step within an agent."""
        self.current_step_index = step_index
        if self.steps:
            self.steps[-1]["current_sub_step"] = step_index
            if description:
                self.current_sub_step = description

    def add_finding(self, label: str, value: str, finding_type: str = "info"):
        """Add a live finding as it's discovered."""
        finding = {
            "label": label,
            "value": value,
            "type": finding_type,  # "info", "success", "warning", "error"
            "timestamp": datetime.now().isoformat(),
            "agent": self.current_agent
        }
        self.live_findings.append(finding)

    def complete(self, output_preview: str = None):
        if self.steps:
            end_time = datetime.now()
            self.steps[-1]["status"] = "completed"
            self.steps[-1]["completed_at"] = end_time.isoformat()
            self.steps[-1]["duration_ms"] = int((end_time - self.start_time).total_seconds() * 1000)
            self.steps[-1]["output_preview"] = output_preview[:200] if output_preview else None
            # Mark all sub-steps as complete
            sub_steps = self.steps[-1].get("sub_steps", [])
            self.steps[-1]["current_sub_step"] = len(sub_steps)

    def fail(self, error: str):
        if self.steps:
            self.steps[-1]["status"] = "failed"
            self.steps[-1]["error"] = error

    def to_dict(self) -> List[Dict]:
        return self.steps

    def get_full_state(self, total_agents: int = 5) -> Dict:
        """Get full progress state including findings and progress percentage."""
        # Calculate agent progress (0-100) within this document
        completed_agents = len([s for s in self.steps if s.get("status") == "completed"])

        # Progress from completed agents
        agent_progress = (completed_agents / total_agents) * 100

        # Add partial progress from current agent's sub-steps
        if self.steps and self.steps[-1].get("status") == "running":
            sub_steps = self.steps[-1].get("sub_steps", [])
            current_sub = self.steps[-1].get("current_sub_step", 0)
            if sub_steps:
                sub_step_progress = (current_sub / len(sub_steps)) * (100 / total_agents)
                agent_progress += sub_step_progress

        return {
            "steps": self.steps,
            "current_agent": self.current_agent,
            "current_sub_step": self.current_sub_step,
            "live_findings": self.live_findings,
            "agent_progress": min(99, agent_progress),  # Cap at 99 until truly complete
            "completed_agents": completed_agents,
            "total_agents": total_agents
        }


# =============================================================================
# AGENT 1: Document Classifier
# =============================================================================
CLASSIFIER_PROMPT = """You are a Lloyd's of London document classification specialist.
Your job is to identify and validate insurance documents.

DOCUMENT TYPES YOU CAN IDENTIFY:
- SLIP: Lloyd's placing slip / Market Reform Contract (MRC)
- POLICY: Full insurance policy document
- CERTIFICATE: Certificate of insurance
- ENDORSEMENT: Policy endorsement/amendment
- QUOTE: Premium quotation
- PROPOSAL: Insurance proposal form
- CLAIM: Claims notification or report
- SURVEY: Risk survey or inspection report
- SCHEDULE: Policy schedule
- RENEWAL: Renewal notice
- COVER_NOTE: Temporary cover note
- BORDEREAU: Premium/claims bordereau
- LOSS_RUN: Loss history report
- NOT_INSURANCE: Not an insurance document

Respond with ONLY valid JSON:
{
    "document_type": "TYPE_FROM_LIST_ABOVE",
    "document_subtype": "More specific classification if applicable",
    "is_valid_insurance_doc": true/false,
    "confidence": 0.0-1.0,
    "lloyd's_market": true/false,
    "document_date": "YYYY-MM-DD or null",
    "reference_numbers": ["Any reference numbers found"],
    "classification_notes": "Brief explanation of classification"
}"""


# =============================================================================
# AGENT 2: Data Extractor
# =============================================================================
EXTRACTOR_PROMPT = """You are a senior Lloyd's data extraction specialist with 20 years experience.
Extract ALL insurance data fields with extreme precision.

REQUIRED FIELDS TO EXTRACT:
{
    "insured": {
        "name": "Legal name of insured",
        "trading_name": "Trading as name if different",
        "address": "Full address",
        "country": "Country",
        "industry": "Industry/SIC code",
        "company_registration": "Company number if shown"
    },
    "broker": {
        "name": "Broker company name",
        "contact": "Contact person",
        "reference": "Broker reference"
    },
    "key_personnel": {
        "directors": [{"name": "Full name", "role": "Director|Managing Director|Chairman"}],
        "officers": [{"name": "Full name", "role": "CEO|CFO|COO|Company Secretary"}],
        "shareholders": [{"name": "Full name or company name", "percentage": numeric or null}],
        "ultimate_beneficial_owners": [{"name": "Full name", "percentage": numeric or null}]
    },
    "coverage": {
        "type": "Property|Liability|Marine|Aviation|Energy|Cyber|Professional|Casualty|Motor|Travel",
        "class_of_business": "Specific class",
        "perils_covered": ["List of covered perils"],
        "territorial_limits": "Geographic scope",
        "basis": "Claims Made|Occurrence|etc"
    },
    "financials": {
        "sum_insured": numeric or null,
        "limit_of_liability": numeric or null,
        "premium": numeric or null,
        "deductible": numeric or null,
        "excess": numeric or null,
        "minimum_premium": numeric or null,
        "deposit_premium": numeric or null,
        "currency": "GBP|USD|EUR|etc"
    },
    "period": {
        "inception_date": "YYYY-MM-DD",
        "expiry_date": "YYYY-MM-DD",
        "period_months": numeric
    },
    "policy_details": {
        "policy_number": "Policy reference",
        "unique_market_reference": "UMR if Lloyd's",
        "placing_broker_contract_ref": "PBCR",
        "lloyd's_risk_code": "Risk code"
    },
    "syndicate_info": {
        "lead_underwriter": "Name",
        "syndicates": ["List of syndicates with lines"],
        "signed_line": "Percentage"
    },
    "claims_info": {
        "claims_notification_period": "Days",
        "claims_contact": "Contact details"
    },
    "special_conditions": ["List of warranties, conditions, subjectivities"],
    "exclusions_noted": ["Key exclusions mentioned"]
}

IMPORTANT: Extract ALL names of directors, officers, shareholders, and UBOs mentioned anywhere in the document.
These are critical for sanctions screening compliance.

Extract exact values. Use null for missing data. Be thorough."""


# =============================================================================
# AGENT 3: Risk Analyst
# =============================================================================
RISK_ANALYST_PROMPT = """You are a Lloyd's risk analyst. Analyze the insurance data and provide a risk assessment.

Return ONLY valid JSON:
{
    "risk_profile": {
        "overall_risk_level": "Low|Medium|High|Very High",
        "risk_score": 0-100,
        "risk_grade": "A|B|C|D|E"
    },
    "exposure_analysis": {
        "natural_catastrophe": {"exposed": true/false, "perils": []},
        "terrorism": {"exposed": true/false},
        "cyber": {"exposed": true/false},
        "supply_chain": {"exposed": true/false}
    },
    "risk_factors": [
        {"factor": "Risk name", "severity": "Low|Medium|High|Critical", "mitigation": "How to address"}
    ],
    "market_comparison": {
        "premium_adequacy": "Adequate|Marginal|Inadequate",
        "rate_comparison": "Below Market|At Market|Above Market"
    },
    "analysis_notes": "Key observations about this risk"
}"""


# =============================================================================
# AGENT 4: Underwriter
# =============================================================================
UNDERWRITER_PROMPT = """You are a senior Lloyd's underwriter. Make a binding decision on this insurance submission.

DECISIONS: GO (accept if confidence >= 60%), NO_GO (decline if confidence < 60%)

Return ONLY valid JSON:
{
    "decision": "GO|NO_GO",
    "confidence": 0.0-1.0,
    "decision_rationale": "Clear explanation of why this decision",
    "appetite_check": {
        "within_appetite": true/false,
        "appetite_notes": "Brief appetite assessment"
    },
    "pricing_assessment": {
        "price_adequacy": "Adequate|Marginal|Inadequate",
        "rate_comment": "Brief pricing view"
    },
    "terms_review": {
        "terms_acceptable": true/false,
        "amendments_needed": ["Any required changes"]
    },
    "recommended_line": "Suggested participation percentage",
    "key_concerns": ["Main issues if any"],
    "strengths": ["Positive aspects of this risk"]
}"""


# =============================================================================
# AGENT 5: Quality Assurance
# =============================================================================
QA_PROMPT = """You are a Lloyd's QA specialist. Review the analysis and verify accuracy.

Return ONLY valid JSON:
{
    "qa_passed": true/false,
    "overall_quality_score": 0.0-1.0,
    "data_quality": {
        "completeness": 0.0-1.0,
        "accuracy_confidence": 0.0-1.0,
        "missing_fields": ["Any critical missing data"]
    },
    "analysis_adequate": true/false,
    "decision_supported": true/false,
    "compliance_check": {
        "sanctions_check_needed": true/false,
        "aml_concerns": true/false
    },
    "final_recommendations": ["Key recommendations"],
    "output_ready": true/false
}"""

# =============================================================================
# AGENT 6: Financial Analyst (DEEP mode only)
# =============================================================================
FINANCIAL_ANALYST_PROMPT = """You are a Lloyd's financial analyst specializing in insurance pricing and capacity.

Analyze the financial aspects of this submission.

Return ONLY valid JSON:
{
    "financial_assessment": {
        "premium_adequacy": "adequate|inadequate|needs_review",
        "rate_assessment": "competitive|below_market|above_market",
        "capacity_utilization": 0.0-1.0
    },
    "pricing_analysis": {
        "technical_rate": 0.0,
        "market_rate_comparison": "above|at|below",
        "pricing_confidence": 0.0-1.0
    },
    "financial_strength": {
        "insured_creditworthy": true/false,
        "payment_risk": "low|medium|high"
    },
    "recommendations": ["Financial recommendations"],
    "confidence": 0.0-1.0
}"""

# =============================================================================
# AGENT 7: Compliance Agent (DEEP mode only)
# =============================================================================
COMPLIANCE_AGENT_PROMPT = """You are a Lloyd's compliance specialist focusing on regulatory and sanctions compliance.

Review this submission for compliance issues.

Return ONLY valid JSON:
{
    "compliance_status": "clear|review_required|blocked",
    "sanctions_screening": {
        "screened": true,
        "matches_found": false,
        "confidence": 0.0-1.0
    },
    "regulatory_compliance": {
        "jurisdiction_approved": true/false,
        "coverage_permitted": true/false,
        "disclosure_adequate": true/false
    },
    "aml_check": {
        "risk_level": "low|medium|high",
        "enhanced_due_diligence": true/false
    },
    "compliance_issues": [],
    "confidence": 0.0-1.0
}"""

# =============================================================================
# AGENT 8: Exposure Analyst (DEEP mode only)
# =============================================================================
EXPOSURE_ANALYST_PROMPT = """You are a Lloyd's exposure analyst specializing in accumulation and catastrophe risk.

Analyze the exposure aspects of this submission.

Return ONLY valid JSON:
{
    "exposure_profile": {
        "primary_exposure": "description",
        "concentration_risk": "low|medium|high",
        "catastrophe_exposure": "low|medium|high"
    },
    "accumulation_analysis": {
        "aggregation_zones": ["zones"],
        "pml_estimate": "percentage of limit",
        "correlation_with_portfolio": "low|medium|high"
    },
    "nat_cat_assessment": {
        "earthquake_exposure": "none|low|moderate|high",
        "flood_exposure": "none|low|moderate|high",
        "windstorm_exposure": "none|low|moderate|high"
    },
    "risk_appetite_fit": "within|borderline|outside",
    "confidence": 0.0-1.0
}"""

# =============================================================================
# AGENT 9: Verification Agent (DEEP mode only)
# =============================================================================
VERIFICATION_AGENT_PROMPT = """You are a Lloyd's verification specialist. Cross-verify all extracted data for accuracy.

Verify the accuracy of extracted data.

Return ONLY valid JSON:
{
    "verification_status": "verified|partial|failed",
    "data_consistency": {
        "names_consistent": true/false,
        "dates_consistent": true/false,
        "amounts_consistent": true/false,
        "coverage_consistent": true/false
    },
    "cross_reference_checks": {
        "insured_name_verified": true/false,
        "broker_details_verified": true/false,
        "coverage_limits_verified": true/false
    },
    "discrepancies_found": [],
    "data_quality_score": 0.0-1.0,
    "confidence": 0.0-1.0
}"""


def fallback_classify_document(document_text: str) -> Dict[str, Any]:
    """
    Keyword-based fallback classification when LLM classifier fails.
    Uses pattern matching to identify document type from content.
    """
    text_lower = document_text.lower()

    # Define keyword patterns for each document type
    patterns = {
        "SLIP": [
            "market reform contract", "mrc", "placing slip", "unique market reference",
            "umr", "lloyd's", "lloyds", "signed line", "leading underwriter",
            "syndicate", "slip reference", "placing broker"
        ],
        "POLICY": [
            "policy wording", "policy document", "terms and conditions",
            "insuring clause", "policy schedule", "whereas the insured",
            "in consideration of the premium", "policy number"
        ],
        "PROPOSAL": [
            "proposal form", "application form", "insurance application",
            "proposer", "declaration by the proposer", "proposed insurance",
            "quotation request", "submission"
        ],
        "CERTIFICATE": [
            "certificate of insurance", "certifies that", "this is to certify",
            "certificate number", "certificate holder"
        ],
        "ENDORSEMENT": [
            "endorsement", "amendment", "addendum", "rider",
            "it is hereby agreed", "policy is amended"
        ],
        "QUOTE": [
            "quotation", "premium indication", "quote reference",
            "quoted premium", "indication", "terms quoted"
        ],
        "CLAIM": [
            "claim notification", "claim form", "loss notification",
            "date of loss", "claim reference", "notice of claim",
            "claims report"
        ],
        "SURVEY": [
            "risk survey", "survey report", "risk engineering",
            "inspection report", "loss prevention", "risk assessment report",
            "surveyor", "site inspection"
        ],
        "SCHEDULE": [
            "schedule of", "list of locations", "schedule of values",
            "asset schedule", "equipment schedule", "vessel schedule"
        ],
        "RENEWAL": [
            "renewal notice", "renewal invitation", "renewal terms",
            "invitation to renew", "renewal premium"
        ],
        "COVER_NOTE": [
            "cover note", "temporary cover", "interim cover",
            "binder", "confirmation of cover"
        ],
        "BORDEREAU": [
            "bordereau", "premium bordereau", "claims bordereau",
            "monthly return", "declaration sheet"
        ],
        "LOSS_RUN": [
            "loss run", "loss history", "claims history", "loss experience",
            "claims summary", "loss ratio", "5-year claims"
        ]
    }

    # Score each document type based on keyword matches
    scores = {}
    for doc_type, keywords in patterns.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[doc_type] = score

    # Determine best match
    if scores:
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        # Calculate confidence based on number of matches (max around 0.7 for fallback)
        confidence = min(0.7, best_score * 0.15)

        # Check for Lloyd's market indicators
        lloyds_keywords = ["lloyd's", "lloyds", "syndicate", "umr", "mrc", "london market"]
        is_lloyds = any(kw in text_lower for kw in lloyds_keywords)

        logger.info(f"Fallback classification: {best_type} (score: {best_score}, confidence: {confidence:.2f})")

        return {
            "document_type": best_type,
            "document_subtype": f"Fallback classified based on {best_score} keyword matches",
            "is_valid_insurance_doc": True,
            "confidence": confidence,
            "lloyd's_market": is_lloyds,
            "document_date": None,
            "reference_numbers": [],
            "classification_notes": f"FALLBACK: LLM classifier failed. Classified using keyword matching with {best_score} matches.",
            "fallback_used": True
        }

    # Default to PROPOSAL if we detect any insurance-related content
    insurance_keywords = ["premium", "insured", "coverage", "deductible", "policy", "underwriting", "broker"]
    if any(kw in text_lower for kw in insurance_keywords):
        logger.info("Fallback classification: Defaulting to PROPOSAL (insurance content detected)")
        return {
            "document_type": "PROPOSAL",
            "document_subtype": "Fallback - general insurance document",
            "is_valid_insurance_doc": True,
            "confidence": 0.4,
            "lloyd's_market": "lloyd" in text_lower or "syndicate" in text_lower,
            "document_date": None,
            "reference_numbers": [],
            "classification_notes": "FALLBACK: LLM classifier failed. Defaulted to PROPOSAL based on insurance terminology.",
            "fallback_used": True
        }

    # No insurance content detected
    logger.warning("Fallback classification: No insurance content detected")
    return {
        "document_type": "NOT_INSURANCE",
        "document_subtype": "Fallback - no insurance keywords found",
        "is_valid_insurance_doc": False,
        "confidence": 0.3,
        "lloyd's_market": False,
        "document_date": None,
        "reference_numbers": [],
        "classification_notes": "FALLBACK: LLM classifier failed. No insurance-related content detected.",
        "fallback_used": True
    }


class AutoGenDocumentProcessor:
    """
    Multi-Agent Document Processing System with Progress Tracking.

    Supports three analysis modes:
    - QUICK: Classifier + Underwriter (fast decision)
    - GO_NO_GO: Classifier + Extractor + Underwriter (standard)
    - DEEP: Full 5-agent pipeline (comprehensive)

    Pipeline:
    1. DocumentClassifier - Identify and validate document
    2. DataExtractor - Extract all insurance fields
    3. RiskAnalyst - Analyze risks and exposures
    4. Underwriter - Make GO/NO-GO/REFER decision
    5. QualityAssurance - Final validation
    """

    def __init__(self, db=None):
        """Initialize processor.

        Args:
            db: Optional database session for tool execution (Gate 5)
        """
        self.llm = _BedrockClientClass()
        self.progress = AgentProgress()
        self.db = db
        self._tool_executor = None

    def _get_tool_executor(self):
        """Get or create tool executor for database operations."""
        if self._tool_executor is None and self.db is not None:
            from app.services.autogen_tools import AutoGenToolExecutor
            self._tool_executor = AutoGenToolExecutor(self.db)
        return self._tool_executor

    async def process_document(
        self,
        document_text: str,
        file_info: str = "",
        progress_callback: Callable = None,
        mode: AnalysisMode = AnalysisMode.DEEP,
        assessment_id: str = None,
    ) -> Dict[str, Any]:
        """
        Process document through agent pipeline with progress tracking.

        Args:
            document_text: The document content to analyze
            file_info: Optional file metadata
            progress_callback: Optional callback for progress updates
            mode: Analysis mode (QUICK, GO_NO_GO, or DEEP)
        """
        agents_to_run = MODE_AGENTS.get(mode, MODE_AGENTS[AnalysisMode.DEEP])
        logger.info(f"Starting {mode.value} analysis with {len(agents_to_run)} agents: {agents_to_run}")
        self.progress = AgentProgress()

        results = {
            "processing_started": datetime.now().isoformat(),
            "analysis_mode": mode.value,
            "agents_used": len(agents_to_run),
            "agent_results": {},
            "progress": [],
            "ocr_extracted_text": document_text,  # Store full OCR text
            "ocr_text_length": len(document_text) if document_text else 0
        }

        # Initialize variables for results compilation
        classification = None
        extraction = None
        risk_analysis = None
        underwriting = None
        qa_result = None
        financial_analysis = {}
        compliance_result = {}
        exposure_result = {}
        verification_result = {}

        try:
            # =========================================================
            # AGENT 1: Document Classifier (Always runs)
            # =========================================================
            if "DocumentClassifier" in agents_to_run:
                self.progress.start("DocumentClassifier", "Identifying document type and validating...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Sub-step 1: Reading documents
                self.progress.update_sub_step(0, "Reading uploaded documents...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())
                await asyncio.sleep(0.3)  # Brief pause to show step

                # Sub-step 2: OCR/Text extraction
                self.progress.update_sub_step(1, "Extracting text from images/PDFs...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())
                await asyncio.sleep(0.3)

                # Sub-step 3: Classifying
                self.progress.update_sub_step(2, "Identifying document types...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Send FULL document text - no truncation for comprehensive classification
                # MiniMax M2.1 has large context, use it fully
                classification = await self._run_agent(
                    CLASSIFIER_PROMPT,
                    f"Classify this insurance document ({len(document_text):,} characters from all uploaded documents):\n\n{document_text}",
                    agent_name="DocumentClassifier"
                )

                # Sub-step 4: Validating
                self.progress.update_sub_step(3, "Validating document structure...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Add live findings from classification
                if classification:
                    doc_type = classification.get("document_type", "UNKNOWN")
                    self.progress.add_finding("Document Type", doc_type, "success")
                    if classification.get("confidence"):
                        conf_pct = f"{int(classification.get('confidence', 0) * 100)}%"
                        self.progress.add_finding("Classification Confidence", conf_pct, "info")
                    if classification.get("lloyd's_market"):
                        self.progress.add_finding("Lloyd's Market", "Yes", "success")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                self.progress.complete(json.dumps(classification)[:200] if classification else None)
                results["agent_results"]["classifier"] = classification

                # FALLBACK: If LLM classifier failed, use keyword-based classification
                if not classification:
                    logger.warning("LLM classifier returned None - using fallback classification")
                    self.progress.add_finding("Classifier", "Using fallback (LLM failed)", "warning")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    classification = fallback_classify_document(document_text)
                    results["agent_results"]["classifier"] = classification
                    results["fallback_classification_used"] = True

                    # Re-add findings from fallback classification
                    doc_type = classification.get("document_type", "UNKNOWN")
                    self.progress.add_finding("Document Type", f"{doc_type} (fallback)", "warning")
                    conf_pct = f"{int(classification.get('confidence', 0) * 100)}%"
                    self.progress.add_finding("Fallback Confidence", conf_pct, "info")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                # Continue processing - don't exit early
                is_valid_insurance = classification.get("is_valid_insurance_doc", False) if classification else False
                results["is_valid_insurance_doc"] = is_valid_insurance

            # =========================================================
            # AGENT 2: Data Extractor (GO_NO_GO and DEEP modes)
            # =========================================================
            if "DataExtractor" in agents_to_run:
                self.progress.start("DataExtractor", "Extracting insurance data fields...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Sub-step 1: Parsing content
                self.progress.update_sub_step(0, "Parsing document content...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())
                await asyncio.sleep(0.3)

                # Sub-step 2: Extracting parties (while running agent)
                self.progress.update_sub_step(1, "Extracting insured & broker names...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Smart extraction - handle large documents with batching and merging
                # If text is too large for single API call, split by document sections and merge
                MAX_CHARS_PER_CALL = 25000  # Safe limit for MiniMax M2.1

                if len(document_text) <= MAX_CHARS_PER_CALL:
                    # Single call for smaller documents
                    extraction = await self._run_agent(
                        EXTRACTOR_PROMPT,
                        f"Document Type: {classification.get('document_type') if classification else 'UNKNOWN'}\n\nExtract ALL data from:\n\n{document_text}",
                        agent_name="DataExtractor"
                    )
                else:
                    # Split by document markers (--- Document N: ---) and process each
                    logger.info(f"Large document ({len(document_text):,} chars) - using smart batching")
                    self.progress.add_finding("Processing", f"Large document: {len(document_text):,} chars - analyzing in sections", "info")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    # Split by document markers
                    import re
                    doc_sections = re.split(r'(--- Document \d+:.*?---)', document_text)

                    # Recombine into document chunks
                    documents = []
                    current_doc = ""
                    for section in doc_sections:
                        if section.startswith('--- Document'):
                            if current_doc:
                                documents.append(current_doc)
                            current_doc = section
                        else:
                            current_doc += section
                    if current_doc:
                        documents.append(current_doc)

                    # If no document markers, split by size
                    if len(documents) <= 1:
                        documents = [document_text[i:i+MAX_CHARS_PER_CALL] for i in range(0, len(document_text), MAX_CHARS_PER_CALL)]

                    logger.info(f"Split into {len(documents)} sections for processing")

                    # Process each section and merge results
                    all_extractions = []
                    for idx, doc_section in enumerate(documents):
                        self.progress.add_finding("Extracting", f"Section {idx+1} of {len(documents)}", "info")
                        if progress_callback:
                            await progress_callback(self.progress.get_full_state())

                        section_extraction = await self._run_agent(
                            EXTRACTOR_PROMPT,
                            f"Document Type: {classification.get('document_type') if classification else 'UNKNOWN'}\n\nExtract ALL data from section {idx+1} of {len(documents)}:\n\n{doc_section}",
                            agent_name="DataExtractor"
                        )
                        if section_extraction:
                            all_extractions.append(section_extraction)

                    # Merge all extractions comprehensively
                    extraction = self._merge_extractions(all_extractions)
                    logger.info(f"Merged {len(all_extractions)} extraction results")

                # Show sub-steps progressing while we process results
                if extraction:
                    # Sub-step 3: Coverage details
                    self.progress.update_sub_step(2, "Extracting coverage details...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    # Add live findings for parties
                    insured = extraction.get("insured", {})
                    if insured.get("name"):
                        self.progress.add_finding("Insured Name", insured.get("name"), "success")
                    broker = extraction.get("broker", {})
                    if broker.get("name"):
                        self.progress.add_finding("Broker", broker.get("name"), "info")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    # Sub-step 4: Financials
                    self.progress.update_sub_step(3, "Extracting premium & limits...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    financials = extraction.get("financials", {})
                    currency = financials.get("currency", "USD")

                    # Helper to safely format numbers (handles dicts, strings, None)
                    def safe_format_number(val, curr):
                        if val is None:
                            return None
                        if isinstance(val, dict):
                            # Handle nested structures like {"amount": 100000}
                            val = val.get("amount") or val.get("value") or str(val)
                        if isinstance(val, (int, float)):
                            return f"{curr} {val:,.0f}"
                        return f"{curr} {val}"

                    premium = financials.get("premium")
                    if premium:
                        formatted = safe_format_number(premium, currency)
                        if formatted:
                            self.progress.add_finding("Premium", formatted, "success")

                    limit = financials.get("sum_insured") or financials.get("limit_of_liability")
                    if limit:
                        formatted = safe_format_number(limit, currency)
                        if formatted:
                            self.progress.add_finding("Sum Insured", formatted, "info")

                    ded = financials.get("deductible") or financials.get("excess")
                    if ded:
                        formatted = safe_format_number(ded, currency)
                        if formatted:
                            self.progress.add_finding("Deductible", formatted, "info")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    # Sub-step 5: Dates
                    self.progress.update_sub_step(4, "Extracting policy dates...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    period = extraction.get("period", {})
                    if period.get("inception_date"):
                        self.progress.add_finding("Inception Date", period.get("inception_date"), "info")
                    if period.get("expiry_date"):
                        self.progress.add_finding("Expiry Date", period.get("expiry_date"), "info")

                    # Sub-step 6: Territory
                    self.progress.update_sub_step(5, "Identifying territory & jurisdiction...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    coverage = extraction.get("coverage", {})
                    if coverage.get("territorial_limits"):
                        self.progress.add_finding("Territory", coverage.get("territorial_limits"), "info")
                    if coverage.get("type"):
                        self.progress.add_finding("Coverage Type", coverage.get("type"), "info")

                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                self.progress.complete(json.dumps(extraction)[:200] if extraction else None)
                results["agent_results"]["extractor"] = extraction

            # =========================================================
            # AGENT 3: Risk Analyst (DEEP mode only)
            # =========================================================
            if "RiskAnalyst" in agents_to_run:
                self.progress.start("RiskAnalyst", "Analyzing risk factors and exposures...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Sub-step 1: Analyzing exposure
                self.progress.update_sub_step(0, "Analyzing exposure profile...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())
                await asyncio.sleep(0.3)

                # Sub-step 2: Nat cat check
                self.progress.update_sub_step(1, "Checking natural catastrophe exposure...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Build risk summary with extracted data AND FULL document text
                risk_summary = self._build_concise_summary(classification, extraction)

                # Process ALL document text - batch if too large, merge results
                MAX_CHARS = 25000
                if document_text and len(document_text) <= MAX_CHARS:
                    # Single pass - send everything
                    risk_summary += f"\n\nFULL DOCUMENT TEXT:\n{document_text}"
                    risk_analysis = await self._run_agent(
                        RISK_ANALYST_PROMPT,
                        f"Analyze this insurance risk thoroughly:\n\n{risk_summary}",
                        agent_name="RiskAnalyst"
                    )
                elif document_text:
                    # Batch processing for large documents
                    logger.info(f"RiskAnalyst: Batching {len(document_text):,} chars")
                    self.progress.add_finding("Processing", f"Large document - analyzing in batches", "info")

                    # Split into chunks
                    chunks = [document_text[i:i+MAX_CHARS] for i in range(0, len(document_text), MAX_CHARS)]
                    all_risk_analyses = []

                    for idx, chunk in enumerate(chunks):
                        chunk_summary = risk_summary + f"\n\nDOCUMENT TEXT (Section {idx+1} of {len(chunks)}):\n{chunk}"
                        chunk_analysis = await self._run_agent(
                            RISK_ANALYST_PROMPT,
                            f"Analyze this insurance risk (section {idx+1}/{len(chunks)}):\n\n{chunk_summary}",
                            agent_name="RiskAnalyst"
                        )
                        if chunk_analysis:
                            all_risk_analyses.append(chunk_analysis)

                    # Merge risk analyses - take highest risk score, combine factors
                    risk_analysis = self._merge_risk_analyses(all_risk_analyses)
                else:
                    risk_analysis = await self._run_agent(
                        RISK_ANALYST_PROMPT,
                        f"Analyze this insurance risk:\n\n{risk_summary}",
                        agent_name="RiskAnalyst"
                    )

                if risk_analysis:
                    # Sub-step 3: Aggregation check
                    self.progress.update_sub_step(2, "Checking aggregation risk...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    # Add exposure findings
                    exposure = risk_analysis.get("exposure_analysis", {})
                    if exposure.get("natural_catastrophe", {}).get("exposed"):
                        perils = exposure.get("natural_catastrophe", {}).get("perils", [])
                        self.progress.add_finding("Nat Cat Exposure", ", ".join(perils) if perils else "Yes", "warning")
                    if exposure.get("cyber", {}).get("exposed"):
                        self.progress.add_finding("Cyber Exposure", "Yes", "warning")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    # Sub-step 4: Scoring
                    self.progress.update_sub_step(3, "Calculating risk score...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    risk_profile = risk_analysis.get("risk_profile", {})
                    if risk_profile.get("risk_score"):
                        score = risk_profile.get("risk_score")
                        score_type = "success" if score < 40 else "warning" if score < 70 else "error"
                        self.progress.add_finding("Risk Score", f"{score}/100", score_type)
                    if risk_profile.get("overall_risk_level"):
                        self.progress.add_finding("Risk Level", risk_profile.get("overall_risk_level"), "info")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    # Sub-step 5: Identifying concerns
                    self.progress.update_sub_step(4, "Identifying risk concerns...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    risk_factors = risk_analysis.get("risk_factors", [])
                    high_risks = [rf for rf in risk_factors if rf.get("severity") in ["High", "Critical"]]
                    if high_risks:
                        for rf in high_risks[:3]:  # Show top 3
                            self.progress.add_finding("Risk Factor", rf.get("factor", "Unknown"), "warning")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                self.progress.complete(json.dumps(risk_analysis)[:200] if risk_analysis else None)
                results["agent_results"]["risk_analyst"] = risk_analysis

                # =========================================================
                # GATE 5: RiskAnalyst ClaimSense Integration
                # =========================================================
                # If assessment_id provided, query ClaimSense for benchmark comparison
                if assessment_id and self.db and mode == AnalysisMode.DEEP:
                    self.progress.add_finding("Benchmark", "Querying ClaimSense data...", "info")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    try:
                        tool_executor = self._get_tool_executor()
                        if tool_executor:
                            # Infer policy type from extraction
                            policy_type = "GL"  # Default
                            coverage = extraction.get("coverage", {}) if extraction else {}
                            ctype = coverage.get("type", "").upper()
                            if "WORKER" in ctype or "WC" in ctype:
                                policy_type = "WC"
                            elif "AUTO" in ctype or "AL" in ctype:
                                policy_type = "AL"
                            elif "PROPERTY" in ctype or "PR" in ctype:
                                policy_type = "PR"

                            # Get state from insured
                            insured = extraction.get("insured", {}) if extraction else {}
                            state = insured.get("state") or insured.get("country")
                            if state and len(state) > 2:
                                state = None  # Only use 2-letter codes

                            benchmark_result = await tool_executor.execute(
                                "compare_insured_to_benchmark",
                                {
                                    "assessment_id": assessment_id,
                                    "policy_type": policy_type,
                                    "state": state,
                                }
                            )
                            benchmark_data = json.loads(benchmark_result)
                            if benchmark_data and not benchmark_data.get("error"):
                                results["agent_results"]["claimsense_benchmark"] = benchmark_data
                                # Add findings
                                narrative = benchmark_data.get("narrative", "")
                                if narrative:
                                    self.progress.add_finding("Benchmark Analysis", narrative[:100] + "...", "info")
                                logger.info(f"ClaimSense benchmark added for assessment {assessment_id}")
                    except Exception as e:
                        logger.warning(f"ClaimSense benchmark failed: {e}")

            # =========================================================
            # GATE 4: Context Summarization (between agents 1-3 and 4+)
            # =========================================================
            # For DEEP mode with large documents, summarize first batch outputs
            # to reduce token costs for remaining agents
            batch1_summary = None
            if mode == AnalysisMode.DEEP and document_text and len(document_text) > 15000:
                self.progress.add_finding("Optimization", "Summarizing context for efficiency", "info")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                batch1_summary = await self._summarize_batch({
                    "classifier": classification,
                    "extractor": extraction,
                    "risk_analyst": risk_analysis,
                })
                if batch1_summary:
                    logger.info(f"Using summarized context for agents 4+: {len(batch1_summary)} chars")
                    results["context_summarization_used"] = True

            # =========================================================
            # AGENT 4a: Financial Analyst (DEEP mode only)
            # =========================================================
            financial_analysis = {}
            if "FinancialAnalyst" in agents_to_run:
                self.progress.start("FinancialAnalyst", "Analyzing financial aspects...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                fin_summary = self._build_concise_summary(classification, extraction)
                # Use batch1 summary if available (Gate 4 optimization), else full document
                if batch1_summary:
                    fin_summary += f"\n\nPRIOR ANALYSIS SUMMARY:\n{batch1_summary}"
                elif document_text:
                    fin_summary += f"\n\nFULL DOCUMENT TEXT:\n{document_text}"
                financial_analysis = await self._run_agent(
                    FINANCIAL_ANALYST_PROMPT,
                    f"Analyze financial aspects thoroughly:\n\n{fin_summary}",
                    agent_name="FinancialAnalyst"
                )

                if financial_analysis:
                    fin_assess = financial_analysis.get("financial_assessment", {})
                    if fin_assess.get("premium_adequacy"):
                        status = "success" if fin_assess["premium_adequacy"] == "adequate" else "warning"
                        self.progress.add_finding("Premium Adequacy", fin_assess["premium_adequacy"], status)
                    pricing = financial_analysis.get("pricing_analysis", {})
                    if pricing.get("pricing_confidence"):
                        self.progress.add_finding("Pricing Confidence", f"{int(pricing['pricing_confidence'] * 100)}%", "info")

                self.progress.complete(json.dumps(financial_analysis)[:200] if financial_analysis else None)
                results["agent_results"]["financial_analyst"] = financial_analysis

            # =========================================================
            # AGENT 4b: Compliance Agent (DEEP mode only)
            # =========================================================
            compliance_result = {}
            if "ComplianceAgent" in agents_to_run:
                self.progress.start("ComplianceAgent", "Checking regulatory compliance...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                comp_summary = self._build_concise_summary(classification, extraction)
                # Use batch1 summary if available (Gate 4 optimization), else full document
                if batch1_summary:
                    comp_summary += f"\n\nPRIOR ANALYSIS SUMMARY:\n{batch1_summary}"
                elif document_text:
                    comp_summary += f"\n\nFULL DOCUMENT TEXT:\n{document_text}"
                compliance_result = await self._run_agent(
                    COMPLIANCE_AGENT_PROMPT,
                    f"Check compliance thoroughly:\n\n{comp_summary}",
                    agent_name="ComplianceAgent"
                )

                if compliance_result:
                    comp_status = compliance_result.get("compliance_status", "review_required")
                    status_type = "success" if comp_status == "clear" else "error" if comp_status == "blocked" else "warning"
                    self.progress.add_finding("Compliance Status", comp_status.upper(), status_type)
                    sanctions = compliance_result.get("sanctions_screening", {})
                    if sanctions.get("screened"):
                        self.progress.add_finding("Sanctions Screened", "Yes", "success")

                self.progress.complete(json.dumps(compliance_result)[:200] if compliance_result else None)
                results["agent_results"]["compliance"] = compliance_result

            # =========================================================
            # AGENT 4c: Exposure Analyst (DEEP mode only)
            # =========================================================
            exposure_result = {}
            if "ExposureAnalyst" in agents_to_run:
                self.progress.start("ExposureAnalyst", "Analyzing exposure profile...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                exp_summary = self._build_concise_summary(classification, extraction)
                # Use batch1 summary if available (Gate 4 optimization), else full document
                if batch1_summary:
                    exp_summary += f"\n\nPRIOR ANALYSIS SUMMARY:\n{batch1_summary}"
                elif document_text:
                    exp_summary += f"\n\nFULL DOCUMENT TEXT:\n{document_text}"
                exposure_result = await self._run_agent(
                    EXPOSURE_ANALYST_PROMPT,
                    f"Analyze exposure thoroughly:\n\n{exp_summary}",
                    agent_name="ExposureAnalyst"
                )

                if exposure_result:
                    exp_profile = exposure_result.get("exposure_profile", {})
                    if exp_profile.get("concentration_risk"):
                        status = "success" if exp_profile["concentration_risk"] == "low" else "warning" if exp_profile["concentration_risk"] == "medium" else "error"
                        self.progress.add_finding("Concentration Risk", exp_profile["concentration_risk"].upper(), status)
                    appetite = exposure_result.get("risk_appetite_fit", "within")
                    self.progress.add_finding("Appetite Fit", appetite.upper(), "success" if appetite == "within" else "warning")

                self.progress.complete(json.dumps(exposure_result)[:200] if exposure_result else None)
                results["agent_results"]["exposure_analyst"] = exposure_result

            # =========================================================
            # AGENT 5: Underwriter (Always runs)
            # =========================================================
            if "Underwriter" in agents_to_run:
                self.progress.start("Underwriter", "Making underwriting decision...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Sub-step 1: Reviewing data
                self.progress.update_sub_step(0, "Reviewing extracted data...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())
                await asyncio.sleep(0.3)

                # Sub-step 2: Checking appetite
                self.progress.update_sub_step(1, "Checking underwriting appetite...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Build underwriting summary with extracted data
                uw_summary = self._build_concise_summary(classification, extraction)

                # Mode-aware text handling:
                # - Quick: Single pass with full text (speed priority)
                # - Go/No-Go & Deep: Batch if needed for thoroughness
                MAX_CHARS = 25000

                if risk_analysis:
                    risk_profile = risk_analysis.get("risk_profile", {})
                    uw_summary += f"\n\nRISK ASSESSMENT:\n- Risk Level: {risk_profile.get('overall_risk_level', 'N/A')}"
                    uw_summary += f"\n- Risk Score: {risk_profile.get('risk_score', 'N/A')}/100"
                    uw_summary += f"\n- Risk Grade: {risk_profile.get('risk_grade', 'N/A')}"
                    if risk_analysis.get("market_comparison", {}).get("premium_adequacy"):
                        uw_summary += f"\n- Premium Adequacy: {risk_analysis['market_comparison']['premium_adequacy']}"

                # Sub-step 3: Assessing pricing
                self.progress.update_sub_step(2, "Assessing premium adequacy...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Process ALL document text - batch if too large
                if document_text and len(document_text) <= MAX_CHARS:
                    # Single pass - send everything
                    full_summary = uw_summary + f"\n\nFULL DOCUMENT TEXT:\n{document_text}"
                    underwriting = await self._run_agent(UNDERWRITER_PROMPT, f"Make underwriting decision based on all available information:\n\n{full_summary}", agent_name="Underwriter")
                elif document_text and len(document_text) > MAX_CHARS:
                    # Batch processing for large documents
                    logger.info(f"Underwriter: Batching {len(document_text):,} chars across sections")
                    self.progress.add_finding("Processing", f"Large document - analyzing thoroughly", "info")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    chunks = [document_text[i:i+MAX_CHARS] for i in range(0, len(document_text), MAX_CHARS)]
                    all_decisions = []

                    for idx, chunk in enumerate(chunks):
                        chunk_summary = uw_summary + f"\n\nDOCUMENT TEXT (Section {idx+1} of {len(chunks)}):\n{chunk}"
                        chunk_decision = await self._run_agent(
                            UNDERWRITER_PROMPT,
                            f"Review this section ({idx+1}/{len(chunks)}) and provide underwriting assessment:\n\n{chunk_summary}",
                            agent_name="Underwriter"
                        )
                        if chunk_decision:
                            all_decisions.append(chunk_decision)

                    # Merge decisions - most conservative wins
                    underwriting = self._merge_underwriting_decisions(all_decisions)
                else:
                    underwriting = await self._run_agent(UNDERWRITER_PROMPT, f"Make underwriting decision:\n\n{uw_summary}", agent_name="Underwriter")

                if underwriting:
                    # Sub-step 4: Applying rules
                    self.progress.update_sub_step(3, "Applying underwriting rules...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    appetite = underwriting.get("appetite_check", {})
                    if appetite.get("within_appetite") is not None:
                        status = "success" if appetite.get("within_appetite") else "warning"
                        self.progress.add_finding("Within Appetite", "Yes" if appetite.get("within_appetite") else "No", status)

                    pricing = underwriting.get("pricing_assessment", {})
                    if pricing.get("price_adequacy"):
                        adequacy = pricing.get("price_adequacy")
                        status = "success" if adequacy == "Adequate" else "warning" if adequacy == "Marginal" else "error"
                        self.progress.add_finding("Price Adequacy", adequacy, status)
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    # Sub-step 5: Making decision
                    self.progress.update_sub_step(4, "Making GO/NO-GO decision...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    decision = underwriting.get("decision", "NO-GO")
                    # Apply 60% threshold
                    confidence = underwriting.get("confidence", 0.5)
                    if confidence < 0.6:
                        decision = "NO-GO"
                    decision_type = "success" if decision == "GO" else "error"
                    self.progress.add_finding("Decision", decision, decision_type)

                    confidence = underwriting.get("confidence", 0)
                    self.progress.add_finding("Confidence", f"{int(confidence * 100)}%", "info")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    # Sub-step 6: Writing rationale
                    self.progress.update_sub_step(5, "Writing decision rationale...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                self.progress.complete(json.dumps(underwriting)[:200] if underwriting else None)
                results["agent_results"]["underwriter"] = underwriting

                # =========================================================
                # GATE 5: Underwriter RapidRate Integration
                # =========================================================
                # If in DEEP mode with adequate data, get actuarial pricing
                if mode == AnalysisMode.DEEP and extraction and self.db:
                    self.progress.add_finding("Pricing", "Calculating actuarial pricing...", "info")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    try:
                        tool_executor = self._get_tool_executor()
                        if tool_executor:
                            # Extract pricing parameters from document data
                            financials = extraction.get("financials", {})
                            insured = extraction.get("insured", {})
                            coverage = extraction.get("coverage", {})

                            # Get exposure (use premium or sum_insured as proxy)
                            exposure = financials.get("premium") or financials.get("sum_insured") or 1000000
                            if isinstance(exposure, dict):
                                exposure = exposure.get("amount", 1000000)
                            exposure = float(exposure) if exposure else 1000000

                            # Infer policy type
                            policy_type = "GL"
                            ctype = (coverage.get("type") or "").upper()
                            if "WORKER" in ctype or "WC" in ctype:
                                policy_type = "WC"
                            elif "AUTO" in ctype or "AL" in ctype:
                                policy_type = "AL"
                            elif "PROPERTY" in ctype or "PR" in ctype:
                                policy_type = "PR"

                            # Get state
                            state = insured.get("state", "CA")
                            if not state or len(state) != 2:
                                state = "CA"  # Default

                            # Get deductible
                            deductible = financials.get("deductible") or financials.get("excess") or 0
                            if isinstance(deductible, dict):
                                deductible = deductible.get("amount", 0)
                            deductible = float(deductible) if deductible else 0

                            # Get limit
                            limit = financials.get("limit_of_liability") or financials.get("sum_insured")
                            if isinstance(limit, dict):
                                limit = limit.get("amount")
                            limit = float(limit) if limit else None

                            pricing_result = await tool_executor.execute(
                                "actuarial_pricing",
                                {
                                    "policy_type": policy_type,
                                    "state": state,
                                    "exposure": exposure,
                                    "deductible": deductible,
                                    "limit": limit,
                                }
                            )
                            pricing_data = json.loads(pricing_result)
                            if pricing_data and not pricing_data.get("error"):
                                results["agent_results"]["rapidrate_pricing"] = pricing_data
                                # Add findings
                                indicated_premium = pricing_data.get("indicated_premium")
                                if indicated_premium:
                                    self.progress.add_finding("Indicated Premium", f"${indicated_premium:,.0f}", "info")
                                logger.info(f"RapidRate pricing added: ${indicated_premium:,.0f}" if indicated_premium else "RapidRate pricing added")
                    except Exception as e:
                        logger.warning(f"RapidRate pricing failed: {e}")

            # =========================================================
            # AGENT 6: Verification Agent (DEEP mode only)
            # =========================================================
            verification_result = {}
            if "VerificationAgent" in agents_to_run:
                self.progress.start("VerificationAgent", "Cross-verifying extracted data...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Use COMPLETE extraction data for thorough verification - no truncation
                verify_summary = f"Verify data consistency across all extracted fields:\n\nComplete Extraction Data:\n{json.dumps(extraction, default=str, indent=2)}"
                verification_result = await self._run_agent(
                    VERIFICATION_AGENT_PROMPT,
                    verify_summary,
                    agent_name="VerificationAgent"
                )

                if verification_result:
                    verify_status = verification_result.get("verification_status", "partial")
                    status_type = "success" if verify_status == "verified" else "warning" if verify_status == "partial" else "error"
                    self.progress.add_finding("Verification", verify_status.upper(), status_type)
                    data_quality = verification_result.get("data_quality_score", 0)
                    self.progress.add_finding("Data Quality", f"{int(data_quality * 100)}%", "info")

                self.progress.complete(json.dumps(verification_result)[:200] if verification_result else None)
                results["agent_results"]["verification"] = verification_result

            # =========================================================
            # AGENT 7: Quality Assurance (DEEP mode only)
            # =========================================================
            if "QualityAssurance" in agents_to_run:
                self.progress.start("QualityAssurance", "Performing final quality check...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Sub-step 1: Checking data
                self.progress.update_sub_step(0, "Checking data completeness...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())
                await asyncio.sleep(0.3)

                # Sub-step 2: Verifying analysis
                self.progress.update_sub_step(1, "Verifying analysis quality...")
                if progress_callback:
                    await progress_callback(self.progress.get_full_state())

                # Use COMPLETE data from all agents for thorough QA - no truncation
                qa_result = await self._run_agent(
                    QA_PROMPT,
                    f"QA Check - Review ALL data for completeness and accuracy:\n\nClassification:\n{json.dumps(classification, default=str, indent=2)}\n\nExtraction:\n{json.dumps(extraction, default=str, indent=2)}\n\nRisk Analysis:\n{json.dumps(risk_analysis, default=str, indent=2)}\n\nUnderwriting Decision:\n{json.dumps(underwriting, default=str, indent=2)}",
                    agent_name="QualityAssurance"
                )

                if qa_result:
                    # Sub-step 3: Compliance check
                    self.progress.update_sub_step(2, "Running compliance checks...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    data_quality = qa_result.get("data_quality", {})
                    completeness = data_quality.get("completeness") or 0
                    self.progress.add_finding("Data Completeness", f"{int(completeness * 100)}%",
                        "success" if completeness > 0.8 else "warning" if completeness > 0.5 else "error")

                    compliance = qa_result.get("compliance_check", {})
                    if compliance.get("sanctions_check_needed"):
                        self.progress.add_finding("Sanctions Check", "Required", "warning")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    # Sub-step 4: Final validation
                    self.progress.update_sub_step(3, "Final validation & sign-off...")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                    qa_passed = qa_result.get("qa_passed", False)
                    self.progress.add_finding("QA Status", "Passed" if qa_passed else "Review Required",
                        "success" if qa_passed else "warning")

                    quality_score = qa_result.get("overall_quality_score", 0)
                    self.progress.add_finding("Quality Score", f"{int(quality_score * 100)}%", "info")
                    if progress_callback:
                        await progress_callback(self.progress.get_full_state())

                self.progress.complete(json.dumps(qa_result)[:200] if qa_result else None)
                results["agent_results"]["qa"] = qa_result

            # =========================================================
            # COMPILE FINAL RESULTS
            # =========================================================
            results["processing_completed"] = datetime.now().isoformat()
            results["progress"] = self.progress.to_dict()

            # Flatten key fields for easy access
            results["is_valid_insurance_doc"] = True
            results["document_type"] = classification.get("document_type")
            results["lloyd's_market"] = classification.get("lloyd's_market", False)

            # Extract key data
            if extraction:
                results["company_name"] = extraction.get("insured", {}).get("name")
                results["risk_type"] = extraction.get("coverage", {}).get("type")
                results["territory"] = extraction.get("coverage", {}).get("territorial_limits")

                financials = extraction.get("financials", {})
                results["premium"] = financials.get("premium")
                results["sum_insured"] = financials.get("sum_insured") or financials.get("limit_of_liability")
                results["deductible"] = financials.get("deductible") or financials.get("excess")
                results["currency"] = financials.get("currency", "GBP")

                period = extraction.get("period", {})
                results["inception_date"] = period.get("inception_date")
                results["expiry_date"] = period.get("expiry_date")

                results["policy_number"] = extraction.get("policy_details", {}).get("policy_number")
                results["broker_name"] = extraction.get("broker", {}).get("name")
                results["broker_reference"] = extraction.get("broker", {}).get("reference")

            # Risk analysis
            if risk_analysis:
                risk_profile = risk_analysis.get("risk_profile", {})
                results["risk_score"] = risk_profile.get("risk_score", 50)
                results["risk_level"] = risk_profile.get("overall_risk_level")
                results["risk_grade"] = risk_profile.get("risk_grade")
                results["risk_factors"] = [rf.get("factor") for rf in risk_analysis.get("risk_factors", [])]

            # Underwriting decision - apply 60% threshold
            if underwriting:
                confidence = underwriting.get("confidence", 0.5)
                decision = underwriting.get("decision", "NO-GO")
                # Below 60% is always NO-GO
                if confidence < 0.6:
                    decision = "NO-GO"
                results["decision"] = decision
                results["decision_rationale"] = underwriting.get("decision_rationale")
                results["pricing_assessment"] = underwriting.get("pricing_assessment")
                results["terms_review"] = underwriting.get("terms_review")

            # QA
            if qa_result:
                results["qa_passed"] = qa_result.get("qa_passed", False)
                results["quality_score"] = qa_result.get("overall_quality_score", 0.5)
                results["output_ready"] = qa_result.get("output_ready", False)

            # Calculate aggregate confidence from all agents
            results["confidence_score"] = self._calculate_aggregate_confidence(
                classification, extraction, risk_analysis, underwriting, qa_result,
                financial_analysis, compliance_result, exposure_result, verification_result
            )

            # Store analysis mode for upgrade tracking
            results["analysis_mode"] = mode.value

            results["autogen_processed"] = True

            logger.info("5-Agent processing complete")
            return results

        except Exception as e:
            logger.error(f"AutoGen processing error: {e}")
            self.progress.fail(str(e))
            results["progress"] = self.progress.to_dict()
            results["error"] = str(e)
            return results

    def _calculate_aggregate_confidence(
        self,
        classification: Dict,
        extraction: Dict,
        risk_analysis: Dict,
        underwriting: Dict,
        qa_result: Dict,
        financial_analysis: Dict = None,
        compliance_result: Dict = None,
        exposure_result: Dict = None,
        verification_result: Dict = None
    ) -> float:
        """
        Calculate weighted average of all agent confidence scores.
        More agents = higher potential confidence (DEEP mode advantage).

        Weights for 9-agent DEEP mode:
        - Classifier: 10%
        - Extractor: 12%
        - Financial Analyst: 10%
        - Risk Analyst: 12%
        - Compliance: 10%
        - Exposure Analyst: 10%
        - Underwriter: 18% (primary decision maker)
        - Verification: 10%
        - QA: 8%
        """
        scores = []
        total_weight = 0

        # Classifier confidence (10%)
        if classification:
            conf = classification.get("confidence", 0.5)
            if isinstance(conf, (int, float)):
                scores.append(float(conf) * 0.10)
                total_weight += 0.10

        # Extractor - use data completeness (12%)
        if extraction:
            filled = 0
            total_fields = 0
            for key in ['insured', 'broker', 'coverage', 'financials', 'period']:
                section = extraction.get(key, {})
                if isinstance(section, dict):
                    for v in section.values():
                        total_fields += 1
                        if v not in [None, {}, [], "", "null"]:
                            filled += 1
            completeness = filled / max(total_fields, 1)
            scores.append(completeness * 0.12)
            total_weight += 0.12

        # Financial Analyst confidence (10%)
        if financial_analysis:
            fin_conf = financial_analysis.get("confidence", 0)
            pricing_conf = financial_analysis.get("pricing_analysis", {}).get("pricing_confidence", 0)
            conf = max(fin_conf, pricing_conf) if fin_conf or pricing_conf else 0.7
            if isinstance(conf, (int, float)):
                scores.append(float(conf) * 0.10)
                total_weight += 0.10

        # Risk Analyst confidence (12%)
        if risk_analysis:
            risk_profile = risk_analysis.get("risk_profile", {})
            risk_score = risk_profile.get("risk_score", 50)
            if isinstance(risk_score, (int, float)):
                risk_conf = 1.0 - (float(risk_score) / 200)
                scores.append(risk_conf * 0.12)
                total_weight += 0.12

        # Compliance Agent confidence (10%)
        if compliance_result:
            comp_conf = compliance_result.get("confidence", 0)
            sanctions_conf = compliance_result.get("sanctions_screening", {}).get("confidence", 0)
            conf = max(comp_conf, sanctions_conf) if comp_conf or sanctions_conf else 0.8
            if isinstance(conf, (int, float)):
                scores.append(float(conf) * 0.10)
                total_weight += 0.10

        # Exposure Analyst confidence (10%)
        if exposure_result:
            exp_conf = exposure_result.get("confidence", 0.7)
            if isinstance(exp_conf, (int, float)):
                scores.append(float(exp_conf) * 0.10)
                total_weight += 0.10

        # Underwriter confidence - primary (18%)
        if underwriting:
            uw_conf = underwriting.get("confidence", 0.5)
            if isinstance(uw_conf, (int, float)):
                scores.append(float(uw_conf) * 0.18)
                total_weight += 0.18

        # Verification Agent confidence (10%)
        if verification_result:
            verify_conf = verification_result.get("confidence", 0)
            data_quality = verification_result.get("data_quality_score", 0)
            conf = max(verify_conf, data_quality) if verify_conf or data_quality else 0.75
            if isinstance(conf, (int, float)):
                scores.append(float(conf) * 0.10)
                total_weight += 0.10

        # QA quality score (8%)
        if qa_result:
            qa_conf = qa_result.get("overall_quality_score", 0.5)
            if isinstance(qa_conf, (int, float)):
                scores.append(float(qa_conf) * 0.08)
                total_weight += 0.08

        # Calculate weighted average
        if total_weight > 0 and scores:
            raw_confidence = sum(scores) / total_weight
            # Boost confidence based on number of agents that contributed
            agent_count_bonus = min(len(scores) / 9.0, 1.0) * 0.1  # Up to 10% bonus for full agent coverage
            return min(raw_confidence + agent_count_bonus, 1.0)

        # Fallback
        if underwriting:
            return float(underwriting.get("confidence", 0.5))
        return 0.5

    def _build_concise_summary(self, classification: Dict, extraction: Dict) -> str:
        """Build a concise text summary for agent prompts (keeps within token limits)."""
        lines = []

        # Document type
        doc_type = classification.get("document_type", "UNKNOWN") if classification else "UNKNOWN"
        lines.append(f"Document Type: {doc_type}")

        if extraction:
            # Insured
            insured = extraction.get("insured", {})
            if insured.get("name"):
                lines.append(f"Insured: {insured.get('name')}")
                if insured.get("country"):
                    lines.append(f"Country: {insured.get('country')}")
                if insured.get("industry"):
                    lines.append(f"Industry: {insured.get('industry')}")

            # Broker
            broker = extraction.get("broker", {})
            if broker.get("name"):
                lines.append(f"Broker: {broker.get('name')}")

            # Coverage
            coverage = extraction.get("coverage", {})
            if coverage.get("type"):
                lines.append(f"Coverage Type: {coverage.get('type')}")
            if coverage.get("class_of_business"):
                lines.append(f"Class: {coverage.get('class_of_business')}")

            # Financials
            financials = extraction.get("financials", {})
            currency = financials.get("currency", "GBP")

            def safe_num(val):
                """Safely format numbers - handles dicts, strings, None"""
                if val is None:
                    return None
                if isinstance(val, dict):
                    val = val.get("amount") or val.get("value") or None
                if val is None:
                    return None
                try:
                    return f"{float(val):,.0f}"
                except (ValueError, TypeError):
                    return str(val)

            sum_insured = safe_num(financials.get("sum_insured"))
            if sum_insured:
                lines.append(f"Sum Insured: {currency} {sum_insured}")
            premium = safe_num(financials.get("premium"))
            if premium:
                lines.append(f"Premium: {currency} {premium}")
            deductible = safe_num(financials.get("deductible"))
            if deductible:
                lines.append(f"Deductible: {currency} {deductible}")

            # Period
            period = extraction.get("period", {})
            if period.get("inception_date"):
                lines.append(f"Inception: {period.get('inception_date')}")
            if period.get("expiry_date"):
                lines.append(f"Expiry: {period.get('expiry_date')}")

            # Key perils
            perils = coverage.get("perils_covered", [])
            if perils:
                lines.append(f"Perils: {', '.join(perils[:5])}")

        return "\n".join(lines)

    async def _summarize_batch(
        self,
        batch_data: Dict[str, Any],
        max_tokens: int = 2000,
    ) -> str:
        """
        Gate 4: Summarize agent outputs to reduce token costs.

        Uses Haiku to create a concise summary of agents 1-3 outputs,
        which is then passed to agents 4+ instead of full document text.

        Args:
            batch_data: Dict with keys like "classifier", "extractor", "risk_analyst"
            max_tokens: Target max tokens for summary (default 2000)

        Returns:
            Condensed summary string
        """
        summary_prompt = """You are a summarization assistant. Create a CONCISE summary of the following insurance document analysis. Focus on:
- Key risk factors and risk score
- Critical financial terms (premium, limits, deductibles)
- Compliance or sanctions concerns
- Main coverage details

Keep the summary under 500 words. Use bullet points for clarity.

ANALYSIS DATA:
"""

        # Build input from batch data
        parts = []
        if batch_data.get("classifier"):
            parts.append(f"CLASSIFICATION:\n{json.dumps(batch_data['classifier'], default=str, indent=2)[:3000]}")
        if batch_data.get("extractor"):
            parts.append(f"EXTRACTION:\n{json.dumps(batch_data['extractor'], default=str, indent=2)[:5000]}")
        if batch_data.get("risk_analyst"):
            parts.append(f"RISK ANALYSIS:\n{json.dumps(batch_data['risk_analyst'], default=str, indent=2)[:3000]}")

        if not parts:
            return ""

        input_text = summary_prompt + "\n\n".join(parts)

        try:
            # Use Haiku for cost-effective summarization
            summary = await self.llm.chat(
                messages=[{"role": "user", "content": input_text}],
                temperature=0.1,
                max_tokens=max_tokens,
                model_id=BEDROCK_MODEL_HAIKU
            )
            if summary:
                logger.info(f"Batch summary created: {len(summary)} chars")
                return summary
        except Exception as e:
            logger.warning(f"Batch summarization failed: {e}")

        # Fallback: use _build_concise_summary
        return self._build_concise_summary(
            batch_data.get("classifier", {}),
            batch_data.get("extractor", {})
        )

    def _merge_extractions(self, extractions: List[Dict]) -> Dict:
        """
        Intelligently merge multiple extraction results.
        Combines data from all sections without losing information.
        """
        if not extractions:
            return {}
        if len(extractions) == 1:
            return extractions[0]

        merged = {}

        def merge_dict(target: Dict, source: Dict, path: str = "") -> Dict:
            """Recursively merge dictionaries, combining lists and preferring non-null values."""
            for key, value in source.items():
                if key not in target or target[key] is None:
                    target[key] = value
                elif isinstance(value, dict) and isinstance(target[key], dict):
                    merge_dict(target[key], value, f"{path}.{key}")
                elif isinstance(value, list) and isinstance(target[key], list):
                    # Combine lists, remove duplicates while preserving order
                    seen = set()
                    combined = []
                    for item in target[key] + value:
                        if isinstance(item, dict):
                            item_key = str(sorted(item.items()))
                        else:
                            item_key = str(item)
                        if item_key not in seen:
                            seen.add(item_key)
                            combined.append(item)
                    target[key] = combined
                elif value is not None and target[key] is None:
                    target[key] = value
                # If both have values, keep the first non-null one (or longer string)
                elif isinstance(value, str) and isinstance(target[key], str):
                    if len(value) > len(target[key]):
                        target[key] = value
            return target

        # Merge all extractions
        for extraction in extractions:
            if extraction:
                merged = merge_dict(merged, extraction)

        logger.info(f"Merged {len(extractions)} extractions into comprehensive result")
        return merged

    def _merge_risk_analyses(self, analyses: List[Dict]) -> Dict:
        """Merge multiple risk analysis results - take worst case for safety."""
        if not analyses:
            return {}
        if len(analyses) == 1:
            return analyses[0]

        # Take highest risk score (most conservative)
        max_score = 0
        worst_level = "Low"
        all_factors = []
        level_order = {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}

        for analysis in analyses:
            profile = analysis.get("risk_profile", {})
            score = profile.get("risk_score", 0)
            if score > max_score:
                max_score = score
            level = profile.get("overall_risk_level", "Low")
            if level_order.get(level, 0) > level_order.get(worst_level, 0):
                worst_level = level

            # Combine all risk factors
            factors = analysis.get("risk_factors", [])
            all_factors.extend(factors)

        # Deduplicate factors
        seen = set()
        unique_factors = []
        for f in all_factors:
            key = f.get("factor", str(f))
            if key not in seen:
                seen.add(key)
                unique_factors.append(f)

        return {
            "risk_profile": {
                "overall_risk_level": worst_level,
                "risk_score": max_score,
                "risk_grade": "E" if max_score > 80 else "D" if max_score > 60 else "C" if max_score > 40 else "B" if max_score > 20 else "A"
            },
            "risk_factors": unique_factors,
            "exposure_analysis": analyses[0].get("exposure_analysis", {}),
            "analysis_notes": f"Comprehensive analysis from {len(analyses)} document sections"
        }

    def _merge_underwriting_decisions(self, decisions: List[Dict]) -> Dict:
        """Merge multiple underwriting decisions - take most conservative."""
        if not decisions:
            return {}
        if len(decisions) == 1:
            return decisions[0]

        # Decision priority: NO_GO > GO (most conservative wins)
        # Below 60% confidence is always NO-GO
        decision_order = {"GO": 1, "NO-GO": 2, "NO_GO": 2}
        final_decision = "GO"
        min_confidence = 1.0
        all_concerns = []
        all_strengths = []
        rationales = []

        for dec in decisions:
            d = dec.get("decision", "NO-GO")
            conf = dec.get("confidence", 0.5)
            # Apply 60% threshold
            if conf < 0.6:
                d = "NO-GO"
            if decision_order.get(d, 2) > decision_order.get(final_decision, 1):
                final_decision = d

            conf = dec.get("confidence", 0.5)
            if conf < min_confidence:
                min_confidence = conf

            all_concerns.extend(dec.get("key_concerns", []))
            all_strengths.extend(dec.get("strengths", []))
            if dec.get("decision_rationale"):
                rationales.append(dec.get("decision_rationale"))

        # Deduplicate
        unique_concerns = list(set(all_concerns))
        unique_strengths = list(set(all_strengths))

        return {
            "decision": final_decision,
            "confidence": min_confidence,
            "decision_rationale": " | ".join(rationales[:3]),
            "key_concerns": unique_concerns,
            "strengths": unique_strengths,
            "appetite_check": decisions[0].get("appetite_check", {}),
            "pricing_assessment": decisions[0].get("pricing_assessment", {}),
            "terms_review": decisions[0].get("terms_review", {}),
            "analysis_note": f"Decision based on {len(decisions)} document sections"
        }

    async def _run_agent(
        self,
        system_prompt: str,
        user_message: str,
        model_id: str = None,
        agent_name: str = None,
    ) -> Optional[Dict]:
        """Run a single agent and parse response.

        Args:
            system_prompt: System prompt for the agent
            user_message: User message to process
            model_id: Optional model ID override (Haiku/Sonnet)
            agent_name: Agent name for logging
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]

            # Use agent-specific model if available
            effective_model = model_id or AGENT_MODEL_MAP.get(agent_name, BEDROCK_MODEL_SONNET)
            if agent_name:
                logger.info(f"Agent {agent_name} using model: {effective_model.split('.')[-1][:30]}")

            response = await self.llm.chat(messages, temperature=0.1, model_id=effective_model)

            if not response:
                logger.warning("Agent returned empty response")
                return None

            return self._parse_json(response)

        except Exception as e:
            logger.error(f"Agent error: {e}")
            return None

    async def _run_agent_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tools: List[Dict],
        tool_executor: "AutoGenToolExecutor",
        model_id: str = None,
        agent_name: str = None,
        max_tool_calls: int = 3,
    ) -> Optional[Dict]:
        """
        Gate 5: Run agent with tool-calling capability.

        If the agent returns a tool_use block, execute the tool and
        feed the result back for the final response.

        Args:
            system_prompt: System prompt for the agent
            user_message: User message to process
            tools: List of tool definitions in Bedrock format
            tool_executor: AutoGenToolExecutor instance
            model_id: Optional model ID override
            agent_name: Agent name for logging
            max_tool_calls: Max number of tool calls per invocation

        Returns:
            Parsed JSON response from agent
        """
        from app.services.autogen_tools import format_tools_for_bedrock

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]

            effective_model = model_id or AGENT_MODEL_MAP.get(agent_name, BEDROCK_MODEL_SONNET)
            if agent_name:
                logger.info(f"Agent {agent_name} (with tools) using model: {effective_model.split('.')[-1][:30]}")

            # Call LLM with tools
            # Note: bedrock_client.chat() needs to support tools parameter
            # For now, we append tool info to system prompt as fallback
            tools_desc = "\n\nAVAILABLE TOOLS:\n"
            for tool in tools:
                tools_desc += f"- {tool['name']}: {tool['description'][:200]}\n"

            messages[0]["content"] = system_prompt + tools_desc + "\n\nIf you need data from these tools, include a <tool_call> block in your response with the tool name and arguments."

            response = await self.llm.chat(messages, temperature=0.1, model_id=effective_model)

            if not response:
                logger.warning(f"Agent {agent_name} returned empty response")
                return None

            # Check if response contains tool call request
            tool_calls_made = 0
            while "<tool_call>" in response and tool_calls_made < max_tool_calls:
                tool_calls_made += 1

                # Parse tool call
                try:
                    import re
                    tool_match = re.search(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', response, re.DOTALL)
                    if tool_match:
                        tool_req = json.loads(tool_match.group(1))
                        tool_name = tool_req.get("tool") or tool_req.get("name")
                        tool_args = tool_req.get("arguments") or tool_req.get("params", {})

                        if tool_name:
                            logger.info(f"Agent {agent_name} calling tool: {tool_name}")

                            # Execute tool
                            tool_result = await tool_executor.execute(tool_name, tool_args)

                            # Continue conversation with tool result
                            messages.append({"role": "assistant", "content": response})
                            messages.append({"role": "user", "content": f"Tool result for {tool_name}:\n{tool_result}\n\nNow provide your final analysis incorporating this data."})

                            response = await self.llm.chat(messages, temperature=0.1, model_id=effective_model)

                            if not response:
                                break
                        else:
                            break
                    else:
                        break
                except Exception as e:
                    logger.warning(f"Tool call parse error: {e}")
                    break

            return self._parse_json(response)

        except Exception as e:
            logger.error(f"Agent with tools error: {e}")
            return None

    def _parse_json(self, content: str) -> Optional[Dict]:
        """Parse JSON from agent response."""
        import re

        if not content:
            logger.warning("_parse_json received empty content")
            return {"_error": "Empty response", "_raw": ""}

        original_content = content

        try:
            content = content.strip()

            # Strategy 1: Extract from ```json blocks
            if "```json" in content:
                parts = content.split("```json")
                if len(parts) > 1:
                    json_part = parts[1].split("```")[0]
                    content = json_part.strip()
            # Strategy 2: Extract from any ``` blocks
            elif "```" in content:
                for part in content.split("```"):
                    part = part.strip()
                    if part.startswith("{") and "}" in part:
                        content = part
                        break

            content = content.strip()

            # Remove control characters that can break JSON parsing
            content = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', content)

            # Try direct parse
            if content.startswith("{"):
                return json.loads(content)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse attempt 1 failed: {e}")

        # Strategy 3: Find JSON object boundaries
        try:
            start = original_content.find('{')
            end = original_content.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = original_content[start:end]
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                # Fix common JSON issues
                json_str = re.sub(r',\s*}', '}', json_str)  # trailing commas
                json_str = re.sub(r',\s*]', ']', json_str)
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse attempt 2 failed: {e}")

        # Strategy 4: Return structured error with raw content for debugging
        logger.error(f"All JSON parse strategies failed. Content preview: {original_content[:500]}")
        return {
            "_error": "JSON parse failed",
            "_raw_preview": original_content[:1000] if original_content else "",
            "summary": "Analysis completed but response format was unexpected. Please review raw output.",
            "recommendation": "NO-GO",
            "confidence": 0.4
        }


# Singleton instance
autogen_processor = AutoGenDocumentProcessor()
