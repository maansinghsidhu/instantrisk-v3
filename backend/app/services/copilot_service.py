"""
InstantRisk V2 - Underwriter Copilot Service

Provides real-time AI guidance to underwriters during the assessment workflow.
Uses LangChain with conversation memory and domain-specific insurance tools.

Architecture:
    CopilotSession → ConversationBufferMemory → LangChain Agent → Bedrock Claude
    Tools: PricingTool, RiskScorerTool, ClauseFinderTool, BenchmarkTool, ComplianceTool

Each underwriter session maintains its own memory context tied to the assessment.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# Session data model
# ============================================================

@dataclass
class CopilotSession:
    """Per-assessment copilot session with conversation history."""
    session_id: str
    assessment_id: str
    user_id: str
    risk_category: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_active: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    message_count: int = 0
    messages: List[Dict[str, str]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)  # Assessment data snapshot


@dataclass
class CopilotSuggestion:
    """A structured suggestion from the copilot."""
    text: str
    suggestion_type: str  # pricing | clause | risk | compliance | general
    confidence: float      # 0.0 - 1.0
    actions: List[Dict[str, str]] = field(default_factory=list)  # Quick actions
    references: List[str] = field(default_factory=list)  # Policy clauses, benchmarks cited


# ============================================================
# Domain tools for the copilot agent
# ============================================================

COPILOT_SYSTEM_PROMPT = """You are an expert Lloyd's of London insurance underwriter copilot with 20+ years of experience.

You assist underwriters in real time during risk assessments. Your role:
1. PRICING: Suggest premium ranges based on risk profile, loss history, and market benchmarks
2. RISK ANALYSIS: Identify key risk factors, accumulations, and correlations
3. CLAUSES: Recommend appropriate policy wordings, endorsements, and exclusions
4. COMPLIANCE: Flag Lloyd's, FCA, PRA, and EIOPA compliance issues
5. BENCHMARKING: Compare submission against historical similar risks

Context about the current assessment:
{assessment_context}

Guidelines:
- Be specific and actionable (not generic insurance advice)
- Reference Lloyd's Market Association (LMA) clause numbers where applicable
- Quote specific risk factors from the assessment data
- Suggest premium adjustments as percentages (e.g., "+15% for poor loss history")
- Always explain your reasoning
- Flag critical issues with [CRITICAL], warnings with [WARNING]
- Respond in the same language as the underwriter

Output format: When suggesting actions, use this structure:
SUGGESTION: <brief headline>
REASONING: <evidence from assessment>
RECOMMENDATION: <specific action>
CONFIDENCE: <High/Medium/Low>
"""

RISK_CATEGORIES = {
    "property": {
        "typical_rate_pml": (0.10, 3.50),  # % of PML
        "key_factors": ["construction type", "fire protection", "flood zone", "occupancy"],
        "common_clauses": ["LMA3100", "LMA3101", "NMA2914"],
    },
    "cyber": {
        "typical_rate_tsi": (0.20, 5.00),  # % of TSI
        "key_factors": ["IT controls", "incident history", "revenue", "data sensitivity"],
        "common_clauses": ["CL380", "NMA2915", "LMA5400"],
    },
    "marine": {
        "typical_rate_tsi": (0.05, 2.00),
        "key_factors": ["vessel age", "flag state", "trading area", "cargo type"],
        "common_clauses": ["MIA1906", "IHC2003", "ITCH1/11/83"],
    },
    "liability": {
        "typical_rate_tsi": (0.15, 4.00),
        "key_factors": ["turnover", "jurisdiction", "claims history", "industry sector"],
        "common_clauses": ["LMA9999", "NMA1477", "LMA5391"],
    },
    "financial_lines": {
        "typical_rate_tsi": (0.50, 8.00),
        "key_factors": ["directors", "financial stability", "regulatory issues", "M&A activity"],
        "common_clauses": ["NMA1780", "LMA5391", "LSW3001"],
    },
}


def _build_assessment_context(assessment_data: Dict[str, Any]) -> str:
    """Format assessment data into a context string for the prompt."""
    lines = []
    if assessment_data.get("title"):
        lines.append(f"Risk: {assessment_data['title']}")
    if assessment_data.get("risk_category"):
        lines.append(f"Category: {assessment_data['risk_category']}")
    if assessment_data.get("insured_name"):
        lines.append(f"Insured: {assessment_data['insured_name']}")
    if assessment_data.get("sum_insured"):
        lines.append(f"Sum Insured: £{assessment_data['sum_insured']:,.0f}")
    if assessment_data.get("premium"):
        lines.append(f"Quoted Premium: £{assessment_data['premium']:,.0f}")
    if assessment_data.get("risk_score"):
        lines.append(f"AI Risk Score: {assessment_data['risk_score']}/100")
    if assessment_data.get("decision"):
        lines.append(f"Current Decision: {assessment_data['decision']}")
    if assessment_data.get("territory"):
        lines.append(f"Territory: {assessment_data['territory']}")
    if assessment_data.get("ai_analysis"):
        analysis = assessment_data["ai_analysis"]
        if isinstance(analysis, dict):
            summary = analysis.get("summary") or analysis.get("executive_summary", "")
            if summary:
                lines.append(f"AI Analysis Summary: {summary[:300]}")
    if assessment_data.get("underwriter_notes"):
        lines.append(f"Underwriter Notes: {assessment_data['underwriter_notes'][:200]}")
    return "\n".join(lines) if lines else "No assessment data provided"


def _get_pricing_guidance(risk_category: str, sum_insured: float, risk_score: int) -> Dict[str, Any]:
    """Generate pricing guidance based on risk category and score."""
    cat = RISK_CATEGORIES.get(risk_category, RISK_CATEGORIES["property"])
    rate_range = cat.get("typical_rate_pml") or cat.get("typical_rate_tsi", (0.1, 3.0))

    # Adjust rates based on risk score
    if risk_score >= 75:  # High risk
        rate_pct = rate_range[0] + (rate_range[1] - rate_range[0]) * 0.8
        loading = "+25-35% risk loading"
    elif risk_score >= 50:  # Medium risk
        rate_pct = rate_range[0] + (rate_range[1] - rate_range[0]) * 0.5
        loading = "+5-15% risk loading"
    else:  # Low risk
        rate_pct = rate_range[0] + (rate_range[1] - rate_range[0]) * 0.2
        loading = "At or below market rate"

    min_premium = sum_insured * rate_range[0] / 100
    max_premium = sum_insured * rate_range[1] / 100
    suggested_premium = sum_insured * rate_pct / 100

    return {
        "min_premium": round(min_premium, 2),
        "max_premium": round(max_premium, 2),
        "suggested_premium": round(suggested_premium, 2),
        "rate_pct": round(rate_pct, 3),
        "loading_note": loading,
        "market_rate_range": f"{rate_range[0]}%-{rate_range[1]}% of sum insured",
        "common_clauses": cat.get("common_clauses", []),
        "key_rating_factors": cat.get("key_factors", []),
    }


def _build_quick_suggestions(
    assessment_data: Dict[str, Any],
    message: str,
) -> List[Dict[str, str]]:
    """Generate quick-action suggestions based on context."""
    suggestions = []
    msg_lower = message.lower()
    risk_score = assessment_data.get("risk_score", 50)
    category = assessment_data.get("risk_category", "property")

    if any(w in msg_lower for w in ["price", "premium", "rate", "pricing"]):
        suggestions.append({
            "type": "pricing",
            "label": "Get pricing benchmarks",
            "action": "What premium range do you suggest for this risk?",
        })
    if any(w in msg_lower for w in ["clause", "wording", "exclusion", "endorsement"]):
        suggestions.append({
            "type": "clause",
            "label": f"Suggest {category} clauses",
            "action": f"What standard clauses should I apply for this {category} risk?",
        })
    if risk_score and risk_score > 65:
        suggestions.append({
            "type": "risk",
            "label": "High-risk mitigation strategies",
            "action": "What risk mitigation measures should I require from the insured?",
        })
    if any(w in msg_lower for w in ["comply", "regulation", "fca", "pra", "lloyd"]):
        suggestions.append({
            "type": "compliance",
            "label": "Check compliance requirements",
            "action": "What Lloyd's and FCA compliance checks apply to this submission?",
        })

    # Default suggestions
    if not suggestions:
        suggestions = [
            {"type": "pricing", "label": "Suggest premium", "action": "What premium do you recommend?"},
            {"type": "risk", "label": "Key risk factors", "action": "What are the top 3 risk factors I should focus on?"},
            {"type": "clause", "label": "Applicable clauses", "action": "Which LMA clauses apply to this risk?"},
        ]

    return suggestions[:4]


# ============================================================
# Copilot Service
# ============================================================

class CopilotService:
    """
    Underwriter AI copilot using LangChain agents with per-session memory.

    Falls back to Bedrock direct calls when LangChain is unavailable.
    Falls back to rule-based guidance when Bedrock is unavailable.
    """

    def __init__(self):
        self._sessions: Dict[str, CopilotSession] = {}
        self._langchain_available = False
        self._bedrock_available = False
        self._check_dependencies()

    def _check_dependencies(self):
        """Check which AI backends are available."""
        try:
            from langchain_anthropic import ChatAnthropic
            self._langchain_available = True
        except ImportError:
            pass

        try:
            from app.services.bedrock_client import get_bedrock_client
            self._bedrock_available = True
        except ImportError:
            pass

        logger.info(
            f"Copilot: langchain={self._langchain_available} bedrock={self._bedrock_available}"
        )

    def create_session(
        self,
        session_id: str,
        assessment_id: str,
        user_id: str,
        risk_category: str,
        assessment_data: Optional[Dict[str, Any]] = None,
    ) -> CopilotSession:
        """Create or replace a copilot session."""
        session = CopilotSession(
            session_id=session_id,
            assessment_id=assessment_id,
            user_id=user_id,
            risk_category=risk_category,
            context=assessment_data or {},
        )
        self._sessions[session_id] = session
        logger.info(f"Copilot session created: {session_id} for assessment {assessment_id}")
        return session

    def get_session(self, session_id: str) -> Optional[CopilotSession]:
        """Get existing session."""
        return self._sessions.get(session_id)

    def list_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """List all active sessions for a user."""
        return [
            {
                "session_id": s.session_id,
                "assessment_id": s.assessment_id,
                "risk_category": s.risk_category,
                "message_count": s.message_count,
                "created_at": s.created_at,
                "last_active": s.last_active,
            }
            for s in self._sessions.values()
            if s.user_id == user_id
        ]

    async def ask(
        self,
        session_id: str,
        message: str,
        assessment_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ask the copilot a question in context of an assessment.

        Args:
            session_id: Copilot session ID
            message: Underwriter's question or request
            assessment_data: Optional fresh assessment snapshot (overrides cached context)

        Returns:
            Dict with answer, suggestions, quick_actions, session info
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Update context if fresh data provided
        if assessment_data:
            session.context.update(assessment_data)

        # Add user message to history
        session.messages.append({"role": "user", "content": message})
        session.message_count += 1
        session.last_active = datetime.now(timezone.utc).isoformat()

        # Build assessment context string
        assessment_context = _build_assessment_context(session.context)
        system_prompt = COPILOT_SYSTEM_PROMPT.format(assessment_context=assessment_context)

        # Try to get AI response
        response_text = None
        ai_backend = "none"

        if self._langchain_available:
            response_text = await self._ask_langchain(session, system_prompt, message)
            ai_backend = "langchain"

        if response_text is None and self._bedrock_available:
            response_text = await self._ask_bedrock(session, system_prompt, message)
            ai_backend = "bedrock"

        if response_text is None:
            response_text = await self._rule_based_response(session, message)
            ai_backend = "rules"

        # Add assistant response to history
        session.messages.append({"role": "assistant", "content": response_text})

        # Generate structured suggestions and quick actions
        suggestions = await self._extract_suggestions(response_text, session.context)
        quick_actions = _build_quick_suggestions(session.context, message)

        return {
            "session_id": session_id,
            "message_count": session.message_count,
            "answer": response_text,
            "suggestions": suggestions,
            "quick_actions": quick_actions,
            "ai_backend": ai_backend,
            "assessment_id": session.assessment_id,
        }

    async def _ask_langchain(
        self,
        session: CopilotSession,
        system_prompt: str,
        message: str,
    ) -> Optional[str]:
        """Ask via LangChain with conversation memory."""
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain.memory import ConversationBufferWindowMemory
            from langchain.schema import HumanMessage, SystemMessage, AIMessage

            # Use Bedrock via anthropic key or direct Anthropic API
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            aws_region = os.getenv("AWS_BEDROCK_REGION", "us-east-1")

            if anthropic_key:
                llm = ChatAnthropic(
                    model="claude-3-5-sonnet-20241022",
                    api_key=anthropic_key,
                    max_tokens=2048,
                    temperature=0.3,
                )
            else:
                # Use Bedrock via LangChain Anthropic (needs ANTHROPIC_API_KEY or AWS config)
                raise ImportError("No Anthropic API key")

            # Build messages from session history (last 10 to keep context manageable)
            lc_messages = [SystemMessage(content=system_prompt)]
            for msg in session.messages[-10:]:
                if msg["role"] == "user":
                    lc_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    lc_messages.append(AIMessage(content=msg["content"]))

            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: llm.invoke(lc_messages)
            )
            return response.content

        except Exception as e:
            logger.debug(f"LangChain ask failed: {e}")
            return None

    async def _ask_bedrock(
        self,
        session: CopilotSession,
        system_prompt: str,
        message: str,
    ) -> Optional[str]:
        """Ask via AWS Bedrock Claude directly."""
        try:
            from app.services.bedrock_client import get_bedrock_client

            client = get_bedrock_client()

            # Build conversation messages (last 10)
            messages = [{"role": "system", "content": system_prompt}]
            for msg in session.messages[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.complete(messages=messages, max_tokens=2048, temperature=0.3),
            )
            return response

        except Exception as e:
            logger.debug(f"Bedrock ask failed: {e}")
            return None

    async def _rule_based_response(
        self,
        session: CopilotSession,
        message: str,
    ) -> str:
        """
        Fallback rule-based copilot responses when AI unavailable.
        Returns structured guidance based on assessment data.
        """
        msg_lower = message.lower()
        ctx = session.context
        category = ctx.get("risk_category", "property")
        risk_score = ctx.get("risk_score", 50) or 50
        sum_insured = ctx.get("sum_insured", 0) or 0
        premium = ctx.get("premium", 0) or 0

        # Pricing questions
        if any(w in msg_lower for w in ["premium", "price", "rate", "pricing", "cost"]):
            if sum_insured > 0:
                guidance = _get_pricing_guidance(category, sum_insured, risk_score)
                return (
                    f"SUGGESTION: Premium guidance for this {category} risk\n\n"
                    f"REASONING: Based on sum insured of £{sum_insured:,.0f} and risk score {risk_score}/100\n\n"
                    f"RECOMMENDATION:\n"
                    f"- Market rate range: {guidance['market_rate_range']}\n"
                    f"- Suggested premium: £{guidance['suggested_premium']:,.0f} ({guidance['rate_pct']:.2f}% of SI)\n"
                    f"- Range: £{guidance['min_premium']:,.0f} – £{guidance['max_premium']:,.0f}\n"
                    f"- Loading: {guidance['loading_note']}\n\n"
                    f"KEY RATING FACTORS: {', '.join(guidance['key_rating_factors'])}\n\n"
                    f"CONFIDENCE: High (rules-based market data)"
                )
            return (
                "Please provide sum insured to calculate premium guidance.\n"
                "For reference, typical market rates:\n"
                "- Property: 0.10-3.50% of PML\n"
                "- Cyber: 0.20-5.00% of TSI\n"
                "- Liability: 0.15-4.00% of TSI"
            )

        # Clause questions
        if any(w in msg_lower for w in ["clause", "wording", "exclusion", "endorsement", "lma"]):
            cat_data = RISK_CATEGORIES.get(category, RISK_CATEGORIES["property"])
            clauses = cat_data.get("common_clauses", [])
            return (
                f"SUGGESTION: Standard clauses for {category} risk\n\n"
                f"RECOMMENDED LMA/NMA CLAUSES:\n"
                + "\n".join(f"- {c}" for c in clauses)
                + "\n\nFor risk score > 70: Consider adding LMA exclusions for poor loss history\n"
                f"For territories outside Lloyd's approved list: Add territorial restriction endorsement\n\n"
                f"CONFIDENCE: High"
            )

        # Risk factor questions
        if any(w in msg_lower for w in ["risk", "factor", "concern", "issue", "flag"]):
            issues = []
            if risk_score >= 75:
                issues.append(f"[CRITICAL] High risk score ({risk_score}/100) - requires senior underwriter sign-off")
            elif risk_score >= 60:
                issues.append(f"[WARNING] Elevated risk score ({risk_score}/100)")

            if not premium and sum_insured:
                issues.append("[WARNING] No premium set - pricing analysis required")

            if not ctx.get("territory"):
                issues.append("[WARNING] Territory not specified - check Lloyd's approved territories")

            if not issues:
                issues.append("No critical risk flags identified at this stage")

            cat_data = RISK_CATEGORIES.get(category, RISK_CATEGORIES["property"])
            return (
                f"RISK FACTOR ANALYSIS:\n\n"
                + "\n".join(f"• {i}" for i in issues)
                + f"\n\nKEY FACTORS TO ASSESS FOR {category.upper()}:\n"
                + "\n".join(f"• {f}" for f in cat_data.get("key_factors", []))
                + "\n\nCONFIDENCE: Medium (rules-based)"
            )

        # Compliance questions
        if any(w in msg_lower for w in ["comply", "compliance", "fca", "pra", "lloyd", "regulatory"]):
            return (
                "COMPLIANCE CHECKLIST for Lloyd's Submission:\n\n"
                "□ Lloyd's Binding Authority / Syndicate capacity confirmed\n"
                "□ FCA authorised broker confirmation received\n"
                "□ Sanctions screening completed (OFAC, HMT, EU)\n"
                "□ Anti-money laundering (AML) checks passed\n"
                "□ PEP/adverse media screening done\n"
                "□ GDPR data handling consented\n"
                "□ Lloyd's minimum information requirements (MIR) met\n"
                "□ Slip/MRC document complete with all mandatory fields\n\n"
                f"For {category} risks, also check:\n"
                "□ Jurisdiction-specific regulatory requirements\n"
                "□ Reinsurance treaty compliance\n\n"
                "CONFIDENCE: High"
            )

        # General / default
        return (
            f"Copilot guidance for {category} assessment:\n\n"
            f"Current assessment data:\n"
            f"• Risk score: {risk_score}/100\n"
            f"• Sum insured: £{sum_insured:,.0f}\n"
            f"• Premium: {'£{:,.0f}'.format(premium) if premium else 'Not set'}\n\n"
            f"Ask me about:\n"
            f"• Premium pricing and rate guidance\n"
            f"• Applicable LMA/NMA clauses\n"
            f"• Risk factors and concerns\n"
            f"• Lloyd's compliance requirements\n"
            f"• Underwriting recommendations"
        )

    async def _extract_suggestions(
        self,
        response_text: str,
        assessment_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Parse structured suggestions from AI response."""
        suggestions = []

        # Look for SUGGESTION: headers
        import re
        suggestion_blocks = re.findall(
            r"SUGGESTION:\s*(.+?)(?=SUGGESTION:|$)", response_text, re.DOTALL
        )

        for block in suggestion_blocks[:3]:
            lines = block.strip().split("\n")
            headline = lines[0].strip()

            # Classify suggestion type
            stype = "general"
            if any(w in headline.lower() for w in ["premium", "price", "rate"]):
                stype = "pricing"
            elif any(w in headline.lower() for w in ["clause", "wording"]):
                stype = "clause"
            elif any(w in headline.lower() for w in ["risk", "factor"]):
                stype = "risk"
            elif any(w in headline.lower() for w in ["comply", "compliance", "regulatory"]):
                stype = "compliance"

            suggestions.append({
                "headline": headline,
                "type": stype,
                "detail": "\n".join(lines[1:]).strip()[:300],
            })

        # If no structured suggestions, generate one from context
        if not suggestions and assessment_data.get("risk_score", 0) > 65:
            suggestions.append({
                "headline": f"High risk score ({assessment_data['risk_score']}) - consider additional loading",
                "type": "pricing",
                "detail": "Risk score above 65 indicates elevated risk profile. Market practice suggests 15-25% loading.",
            })

        return suggestions

    async def get_pre_submission_checklist(
        self,
        assessment_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a pre-submission checklist based on assessment data.
        Returns required actions before final underwriting sign-off.
        """
        category = assessment_data.get("risk_category", "property")
        risk_score = assessment_data.get("risk_score", 50) or 50
        checks = []

        # Universal Lloyd's checks
        universal = [
            ("sanctions", "Sanctions screening (OFAC/HMT/EU)", "required"),
            ("aml", "Anti-Money Laundering (AML) verification", "required"),
            ("broker_auth", "FCA-authorised broker confirmation", "required"),
            ("mrc", "MRC/slip document completeness", "required"),
            ("sum_insured", "Sum insured adequacy check", "required"),
            ("inception", "Policy inception/expiry dates confirmed", "required"),
        ]
        for key, label, status in universal:
            val = assessment_data.get(key)
            checks.append({
                "id": key,
                "label": label,
                "status": "complete" if val else "pending",
                "priority": "critical",
            })

        # Risk-score dependent checks
        if risk_score >= 70:
            checks.append({
                "id": "senior_approval",
                "label": f"Senior underwriter sign-off (risk score {risk_score})",
                "status": "pending",
                "priority": "critical",
            })

        # Category-specific
        if category == "cyber":
            checks.extend([
                {"id": "it_controls", "label": "IT security controls assessment", "status": "pending", "priority": "high"},
                {"id": "mfa", "label": "Multi-factor authentication confirmed", "status": "pending", "priority": "high"},
                {"id": "backup", "label": "Backup/recovery procedures verified", "status": "pending", "priority": "medium"},
            ])
        elif category == "property":
            checks.extend([
                {"id": "survey", "label": "Property survey/inspection completed", "status": "pending", "priority": "high"},
                {"id": "fire_protection", "label": "Fire protection system confirmed", "status": "pending", "priority": "high"},
                {"id": "flood_zone", "label": "Flood zone assessment done", "status": "pending", "priority": "medium"},
            ])
        elif category == "liability":
            checks.extend([
                {"id": "loss_run", "label": "5-year loss run received", "status": "pending", "priority": "high"},
                {"id": "financials", "label": "Financial statements reviewed", "status": "pending", "priority": "medium"},
            ])

        completed = sum(1 for c in checks if c["status"] == "complete")
        total = len(checks)

        return {
            "assessment_id": assessment_data.get("id", ""),
            "risk_category": category,
            "checklist": checks,
            "completion_pct": round((completed / total * 100) if total else 0, 1),
            "completed": completed,
            "total": total,
            "ready_for_submission": completed >= (total * 0.8),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_pricing_analysis(
        self,
        assessment_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate detailed pricing analysis for an assessment."""
        category = assessment_data.get("risk_category", "property")
        risk_score = assessment_data.get("risk_score", 50) or 50
        sum_insured = assessment_data.get("sum_insured", 0) or 0
        current_premium = assessment_data.get("premium", 0) or 0

        if sum_insured <= 0:
            return {
                "error": "Sum insured is required for pricing analysis",
                "assessment_id": assessment_data.get("id", ""),
            }

        guidance = _get_pricing_guidance(category, sum_insured, risk_score)

        # Rate-on-line calculation
        rol = (current_premium / sum_insured * 100) if current_premium and sum_insured else None

        # Assessment vs market
        market_adequacy = None
        if current_premium and guidance["suggested_premium"]:
            ratio = current_premium / guidance["suggested_premium"]
            if ratio < 0.85:
                market_adequacy = "BELOW_MARKET"
            elif ratio > 1.20:
                market_adequacy = "ABOVE_MARKET"
            else:
                market_adequacy = "AT_MARKET"

        return {
            "assessment_id": assessment_data.get("id", ""),
            "risk_category": category,
            "risk_score": risk_score,
            "sum_insured": sum_insured,
            "current_premium": current_premium,
            "rate_on_line_pct": round(rol, 3) if rol else None,
            "pricing_guidance": guidance,
            "market_adequacy": market_adequacy,
            "recommendation": (
                f"Premium appears {'adequate' if market_adequacy == 'AT_MARKET' else market_adequacy.lower().replace('_', ' ')}"
                f". Suggested: £{guidance['suggested_premium']:,.0f}"
            ) if market_adequacy else "Set premium to generate pricing recommendation",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def close_session(self, session_id: str) -> bool:
        """Close and remove a copilot session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def cleanup_old_sessions(self, max_age_hours: int = 8):
        """Remove sessions older than max_age_hours."""
        now = datetime.now(timezone.utc)
        to_delete = []
        for sid, s in self._sessions.items():
            try:
                last = datetime.fromisoformat(s.last_active)
                age_hours = (now - last).total_seconds() / 3600
                if age_hours > max_age_hours:
                    to_delete.append(sid)
            except Exception:
                pass
        for sid in to_delete:
            del self._sessions[sid]
        return len(to_delete)


# Singleton
_copilot_service: Optional[CopilotService] = None


def get_copilot_service() -> CopilotService:
    """Get or create the CopilotService singleton."""
    global _copilot_service
    if _copilot_service is None:
        _copilot_service = CopilotService()
    return _copilot_service
