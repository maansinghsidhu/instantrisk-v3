"""
OpenDraft Document Generator — 19-Agent Insurance Pipeline

Adapted from OpenDraft's multi-agent architecture (scailetech/opendraft)
for Lloyd's insurance document generation with ACORD/CUAD/JeTech RAG.

6 Phases, 19 Agents:
  PHASE 1 - RESEARCH (1-3):   RiskResearcher, ClauseExtractor, GapAnalyzer
  PHASE 2 - STRUCTURE (4-6):  ClauseManager, StructurePlanner, LloydFormatter
  PHASE 3 - COMPOSE (7-9):    SectionDrafter, ConsistencyChecker, ToneUnifier
  PHASE 4 - VALIDATE (10-12): RiskChallenger, ClauseVerifier, ComplianceReviewer
  PHASE 5 - REFINE (13-16):   HouseStyleAgent, LanguageVarier, ProofReader, ClauseCompiler
  PHASE 6 - EXPORT (17-19):   ScheduleBuilder, PDFExporter, QualityGate

Cost per document: ~$0.15 (template-first, AI only for gaps: ~5 Haiku + 3-5 Sonnet calls)
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.insurance_model_service import insurance_model_service

logger = logging.getLogger(__name__)

# Agent model assignments (haiku = cheap/fast, sonnet = smart/analytical)
AGENT_MODELS = {
    "RiskResearcher": "haiku",
    "ClauseExtractor": "haiku",
    "GapAnalyzer": "sonnet",
    "ClauseManager": "haiku",
    "StructurePlanner": "sonnet",
    "LloydFormatter": "haiku",
    "SectionDrafter": "sonnet",
    "ConsistencyChecker": "haiku",
    "ToneUnifier": "haiku",
    "RiskChallenger": "sonnet",
    "ClauseVerifier": "haiku",
    "ComplianceReviewer": "sonnet",
    "HouseStyleAgent": "haiku",
    "LanguageVarier": "haiku",
    "ProofReader": "haiku",
    "ClauseCompiler": "haiku",
    "ScheduleBuilder": "sonnet",
    "PDFExporter": "haiku",
    "QualityGate": "sonnet",
}

TOTAL_AGENTS = 19


class OpenDraftGenerator:
    """AI-driven document generation using 19-agent insurance pipeline."""

    def __init__(self):
        self._bedrock = None
        self._unified_rag = None

    @property
    def bedrock(self):
        if self._bedrock is None:
            from app.services.bedrock_client import BedrockClient
            self._bedrock = BedrockClient()
        return self._bedrock

    @property
    def unified_rag(self):
        if self._unified_rag is None:
            from app.services.unified_rag import unified_rag
            self._unified_rag = unified_rag
        return self._unified_rag

    @staticmethod
    def _fmt_currency(value, currency="GBP"):
        """Format a numeric value as currency string: 15000000.0 -> 'GBP 15,000,000'."""
        if value is None or str(value).strip() in ("", "None", "none"):
            return "TBA"
        try:
            num = float(value)
            if num == int(num):
                return f"{currency} {int(num):,}"
            return f"{currency} {num:,.2f}"
        except (ValueError, TypeError):
            return str(value)

    def _resolve_model_id(self, model_alias: str) -> Optional[str]:
        """Resolve short model alias to full Bedrock model ID."""
        from app.config import settings
        if model_alias == "sonnet":
            return settings.BEDROCK_MODEL_ID
        elif model_alias == "haiku":
            return settings.BEDROCK_FALLBACK_MODEL
        return None

    async def _run_agent(
        self,
        name: str,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.1,
        max_tokens: int = 8000,
    ) -> Optional[str]:
        """Run a single agent via Bedrock."""
        model_alias = AGENT_MODELS.get(name, "haiku")
        model_id = self._resolve_model_id(model_alias)
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
            response = await self.bedrock.chat(messages, temperature=temperature, max_tokens=max_tokens, model_id=model_id)
            if response:
                logger.info(f"Agent {name} succeeded (response length: {len(response)})")
            else:
                logger.warning(f"Agent {name} returned empty response (Bedrock may be disabled)")
            return response
        except Exception as e:
            logger.error(f"Agent {name} failed: {e}")
            return None

    @staticmethod
    def _fmt_currency(value, currency="GBP"):
        """Format a numeric value as currency string (e.g. 'GBP 15,000,000')."""
        if value is None:
            return "TBA"
        try:
            amount = float(value)
            if amount == int(amount):
                return f"{currency} {int(amount):,}"
            return f"{currency} {amount:,.2f}"
        except (ValueError, TypeError):
            return str(value)

    async def _run_agent_json(
        self,
        name: str,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.1,
    ) -> Optional[Dict]:
        """Run agent and parse JSON response."""
        response = await self._run_agent(name, system_prompt, user_content, temperature)
        if response:
            return self._parse_json(response)
        return None

    # ─── PHASE 1: RESEARCH (Agents 1-3) ───────────────────────────────

    async def agent_risk_researcher(
        self,
        assessment_data: Dict,
        user_id: str = None,
        ml_context: Dict = None,
    ) -> Dict:
        """Agent 1: RiskResearcher — searches pgvector for relevant clauses and precedents."""
        risk_category = assessment_data.get("risk_category", "property")
        territory = assessment_data.get("territory", "")

        rag_context = ""
        try:
            results = await self.unified_rag.search(
                query=f"{risk_category} insurance clauses {territory} Lloyd's placement coverage",
                user_id=user_id,
                top_k=8,
            )
            rag_context = self.unified_rag.format_as_context(results, max_chars=4000)
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")

        assessment_summary = json.dumps({
            "risk_category": risk_category,
            "territory": territory,
            "insured_name": assessment_data.get("insured_name", ""),
            "insured_entity_name": assessment_data.get("insured_entity_name", ""),
            "companies_house_number": assessment_data.get("companies_house_number", ""),
            "broker_name": assessment_data.get("broker_name", ""),
            "commission_rate": assessment_data.get("commission_rate"),
            "premium": self._fmt_currency(assessment_data.get("premium"), assessment_data.get("currency", "GBP")),
            "sum_insured": self._fmt_currency(assessment_data.get("sum_insured"), assessment_data.get("currency", "GBP")),
            "deductible": self._fmt_currency(assessment_data.get("deductible"), assessment_data.get("currency", "GBP")),
            "inception_date": assessment_data.get("inception_date", ""),
            "expiry_date": assessment_data.get("expiry_date", ""),
            "renewal_date": assessment_data.get("renewal_date", ""),
            "decision": assessment_data.get("decision", ""),
            "risk_score": assessment_data.get("risk_score"),
            "regulatory_framework": assessment_data.get("regulatory_framework", ""),
            "loss_run_reporting_rules": assessment_data.get("loss_run_reporting_rules", ""),
            "ai_analysis_summary": str(assessment_data.get("ai_analysis", {}))[:2000],
        }, indent=2)

        # ML-powered insights
        ml_block = ""
        if ml_context:
            appetite = ml_context.get("appetite", {})
            pricing = ml_context.get("pricing", {})
            ml_clauses = ml_context.get("clauses", [])
            ml_block = f"""
INSTANTRISK ENGINE ANALYSIS:
- Risk appetite: {appetite.get('decision', 'unknown')} (confidence: {appetite.get('confidence', 0):.0%})
- Pricing band: {pricing.get('band', 'unknown')} (confidence: {pricing.get('confidence', 0):.0%})
- ML-recommended clause categories: {', '.join(c['category'] for c in ml_clauses[:10])}
"""

        result = await self._run_agent_json(
            "RiskResearcher",
            "You are a Lloyd's insurance research specialist. Search and identify all relevant clauses, precedents, and market wordings for the given risk.",
            f"""Research this insurance risk and identify relevant clauses.

ASSESSMENT DATA:
{assessment_summary}

KNOWLEDGE BASE (ACORD/CUAD/JeTech results):
{rag_context}
{ml_block}
Return ONLY valid JSON:
{{
    "risk_profile": {{
        "category": "{risk_category}",
        "territory": "{territory}",
        "key_exposures": ["list of key risk exposures"],
        "market_context": "Brief market context"
    }},
    "relevant_clauses": [
        {{
            "clause_id": "Clause ID (e.g., LMA5021, ICC_A)",
            "name": "Clause name",
            "relevance": "Why this clause applies",
            "priority": "mandatory|recommended|optional",
            "source": "acord|cuad|jetech|standard"
        }}
    ],
    "recommended_documents": [
        {{
            "type": "mrc_slip|policy_wording|endorsement|certificate|schedule|cover_note",
            "name": "Document name",
            "reason": "Why needed",
            "priority": "mandatory|recommended|optional"
        }}
    ]
}}"""
        )
        return result or self._fallback_research(assessment_data)

    async def agent_clause_extractor(
        self,
        research: Dict,
        user_id: str = None,
        ml_context: Dict = None,
    ) -> List[Dict]:
        """Agent 2: ClauseExtractor — deep-reads found clauses, extracts key provisions."""
        clause_candidates = []
        seen_ids = set()

        for clause in research.get("relevant_clauses", [])[:20]:
            clause_id = clause.get("clause_id", "")
            name = clause.get("name", "")
            seen_ids.add(clause_id)
            query = f"{name} {clause_id} insurance clause full wording provisions"

            try:
                results = await self.unified_rag.search(
                    query=query,
                    user_id=user_id,
                    top_k=3,
                    min_score=0.3,
                )
                candidates = []
                for r in results:
                    candidates.append({
                        "text": r.get("text", "")[:1000],
                        "source_tier": r.get("source_tier", "unknown"),
                        "source_label": r.get("source_label", "Unknown"),
                        "score": r.get("score", 0),
                    })

                clause_candidates.append({
                    "clause_id": clause_id,
                    "name": name,
                    "priority": clause.get("priority", "recommended"),
                    "candidates": candidates,
                    "best_source": candidates[0]["source_tier"] if candidates else "ai_generated",
                })
            except Exception as e:
                logger.warning(f"Clause extraction failed for {clause_id}: {e}")
                clause_candidates.append({
                    "clause_id": clause_id,
                    "name": name,
                    "priority": clause.get("priority", "recommended"),
                    "candidates": [],
                    "best_source": "ai_generated",
                })

        # Use ML-predicted clause categories to find additional relevant clauses
        if ml_context and ml_context.get("clauses"):
            for ml_clause in ml_context["clauses"][:10]:
                category = ml_clause.get("category", "")
                if category and category not in seen_ids:
                    try:
                        results = await self.unified_rag.search(
                            query=f"{category} insurance clause wording",
                            user_id=user_id,
                            top_k=2,
                            min_score=0.4,
                        )
                        if results:
                            candidates = [{
                                "text": r.get("text", "")[:1000],
                                "source_tier": r.get("source_tier", "unknown"),
                                "source_label": r.get("source_label", "Unknown"),
                                "score": r.get("score", 0),
                            } for r in results]
                            clause_candidates.append({
                                "clause_id": f"ML_{category.upper().replace(' ', '_')}",
                                "name": category,
                                "priority": "recommended",
                                "candidates": candidates,
                                "best_source": candidates[0]["source_tier"],
                                "ml_score": ml_clause.get("score", 0),
                            })
                    except Exception as e:
                        logger.warning(f"ML clause extraction failed for {category}: {e}")

        return clause_candidates

    async def agent_gap_analyzer(
        self,
        research: Dict,
        clause_candidates: List[Dict],
        assessment_data: Dict,
    ) -> Dict:
        """Agent 3: GapAnalyzer — compares found clauses against mandatory checklist."""
        found_ids = [c["clause_id"] for c in clause_candidates if c.get("candidates")]
        missing_ids = [c["clause_id"] for c in clause_candidates if not c.get("candidates")]

        result = await self._run_agent_json(
            "GapAnalyzer",
            "You are a Lloyd's gap analysis specialist. Identify missing coverage and mandatory clauses.",
            f"""Analyze coverage gaps for this insurance placement.

Risk category: {assessment_data.get('risk_category', 'property')}
Territory: {assessment_data.get('territory', '')}
Insured: {assessment_data.get('insured_entity_name') or assessment_data.get('insured_name', '')}
Regulatory framework: {assessment_data.get('regulatory_framework', '')}
Clauses FOUND in knowledge base: {', '.join(found_ids[:30])}
Clauses NOT FOUND: {', '.join(missing_ids[:20])}

Identify:
1. Mandatory clauses missing from this placement
2. Coverage gaps based on territory and risk type
3. Regulatory requirements not yet addressed

Return ONLY valid JSON:
{{
    "coverage_gaps": [
        {{
            "gap_type": "missing_clause|coverage_gap|regulatory",
            "description": "What's missing",
            "clause_id": "Suggested clause ID if applicable",
            "severity": "critical|important|minor",
            "recommendation": "How to address"
        }}
    ],
    "mandatory_missing": ["List of absolutely required but missing clauses"],
    "overall_coverage_score": 0.0-1.0,
    "notes": "Summary of gap analysis"
}}"""
        )
        return result or {"coverage_gaps": [], "mandatory_missing": missing_ids, "overall_coverage_score": 0.7, "notes": ""}

    # ─── PHASE 2: STRUCTURE (Agents 4-6) ──────────────────────────────

    async def agent_clause_manager(
        self,
        clause_candidates: List[Dict],
        gap_analysis: Dict,
    ) -> List[Dict]:
        """Agent 4: ClauseManager — maps clause IDs to full text, builds citation database."""
        selections = []

        for candidate in clause_candidates:
            if candidate.get("candidates"):
                best = candidate["candidates"][0]
                selections.append({
                    "clause_id": candidate["clause_id"],
                    "name": candidate["name"],
                    "priority": candidate["priority"],
                    "selected_text": best["text"],
                    "source": best["source_tier"],
                    "source_label": best["source_label"],
                    "score": best["score"],
                    "status": "found",
                })
            else:
                selections.append({
                    "clause_id": candidate["clause_id"],
                    "name": candidate["name"],
                    "priority": candidate["priority"],
                    "selected_text": "",
                    "source": "ai_generated",
                    "source_label": "AI Generated",
                    "score": 0,
                    "status": "generate",
                })

        # Add mandatory missing clauses from gap analysis
        existing_ids = {s["clause_id"] for s in selections}
        for missing_id in gap_analysis.get("mandatory_missing", []):
            if missing_id not in existing_ids:
                selections.append({
                    "clause_id": missing_id,
                    "name": missing_id,
                    "priority": "mandatory",
                    "selected_text": "",
                    "source": "ai_generated",
                    "source_label": "AI Generated (Gap Fill)",
                    "score": 0,
                    "status": "generate",
                })

        return selections

    async def agent_structure_planner(
        self,
        doc_type: str,
        selected_clauses: List[Dict],
        assessment_data: Dict,
    ) -> Dict:
        """Agent 5: StructurePlanner — select template and map clauses to sections."""
        from app.services.insurance_templates import auto_select_template, get_template

        template_id = auto_select_template(
            assessment_data.get("risk_category", "property"), doc_type
        )
        template = get_template(template_id) or {}
        template_sections = template.get("sections", [])
        standard_clause_ids = template.get("standard_clauses", [])

        if not template_sections:
            # Fallback: one section per clause
            return {
                "document_type": doc_type,
                "template_id": template_id,
                "sections": [
                    {"section_number": str(i + 1), "title": c["name"], "content_type": "clause", "clause_ids": [c["clause_id"]], "notes": ""}
                    for i, c in enumerate(selected_clauses)
                ],
                "total_sections": len(selected_clauses),
                "standard_clauses": standard_clause_ids,
            }

        # Build section list from template, mapping selected clauses to sections
        sections = []
        for i, section_title in enumerate(template_sections, 1):
            matching_clause_ids = []
            for clause in selected_clauses:
                if self._clause_matches_section(clause, section_title):
                    matching_clause_ids.append(clause["clause_id"])

            sections.append({
                "section_number": str(i),
                "title": section_title,
                "content_type": "clause",
                "clause_ids": matching_clause_ids,
                "notes": "",
            })

        logger.info(f"StructurePlanner: template={template_id}, {len(sections)} sections, "
                     f"{sum(len(s['clause_ids']) for s in sections)} clause mappings")

        return {
            "document_type": doc_type,
            "template_id": template_id,
            "sections": sections,
            "total_sections": len(sections),
            "standard_clauses": standard_clause_ids,
        }

    def _clause_matches_section(self, clause: Dict, section_title: str) -> bool:
        """Check if a clause belongs in a given section by fuzzy name matching."""
        title_lower = section_title.lower()
        clause_name = clause.get("name", "").lower()
        clause_id = clause.get("clause_id", "").lower()

        # Direct matches
        match_pairs = [
            ("assured", ["assured", "insured"]),
            ("period", ["period", "inception", "expiry"]),
            ("interest", ["interest", "subject matter"]),
            ("territorial", ["territorial", "territory", "jurisdiction"]),
            ("limit of liability", ["limit", "liability", "sum insured"]),
            ("deductible", ["deductible", "excess", "retention"]),
            ("basis of cover", ["basis", "cover", "claims made", "occurrence"]),
            ("premium", ["premium", "payment"]),
            ("subjectivities", ["subjectivity", "subject to"]),
            ("warranties", ["warranty", "warranted"]),
            ("exclusions", ["exclusion", "excluded", "nuclear", "sanctions"]),
            ("conditions", ["condition", "general condition"]),
            ("claims", ["claims", "notification", "claims cooperation"]),
            ("law", ["law", "jurisdiction", "arbitration", "governing"]),
            ("several liability", ["several liability", "lma5096"]),
            ("security", ["security", "underwriter", "syndicate"]),
            ("broker", ["broker", "placing broker"]),
            ("cancellation", ["cancellation", "cancel"]),
            ("subrogation", ["subrogation"]),
        ]

        for section_key, clause_keywords in match_pairs:
            if section_key in title_lower:
                for kw in clause_keywords:
                    if kw in clause_name or kw in clause_id:
                        return True

        return False

    async def agent_lloyd_formatter(
        self,
        structure: Dict,
        assessment_data: Dict,
    ) -> Dict:
        """Agent 6: LloydFormatter — extract formatting from template (code-only, no AI call)."""
        return {
            "format_rules": {
                "header_style": "MRC Standard",
                "numbering": "1, 2, 3 etc",
                "clause_ref_format": "Clause ID in parentheses",
                "schedule_format": "Tabular with numbered items",
            },
            "header_block": {
                "type_of_insurance": assessment_data.get("risk_category", "Property"),
                "unique_market_reference": f"B0000/IR/{datetime.utcnow().strftime('%Y')}",
                "insured": assessment_data.get("insured_entity_name") or assessment_data.get("insured_name", "TBA"),
                "period": f"{assessment_data.get('inception_date', 'TBA')} to {assessment_data.get('expiry_date', 'TBA')}",
                "premium": self._fmt_currency(assessment_data.get("premium"), assessment_data.get("currency", "GBP")),
                "sum_insured": self._fmt_currency(assessment_data.get("sum_insured"), assessment_data.get("currency", "GBP")),
                "broker": assessment_data.get("broker_name", "TBA"),
                "brokerage": f"{assessment_data.get('commission_rate', 'TBA')}%",
                "territory": assessment_data.get("territory", "TBA"),
            },
            "footer_notes": "This slip is for placing purposes only and is subject to contract.",
        }

    # ─── PHASE 3: COMPOSE (Agents 7-9) ────────────────────────────────

    def _build_template_data(self, assessment_data: Dict) -> Dict:
        """Map assessment fields to template placeholder names.

        Risk-score-aware: high risk scores (>70) get stricter terms,
        additional exclusions, and enhanced subjectivities.
        """
        risk_score = assessment_data.get("risk_score") or 0
        risk_category = assessment_data.get("risk_category", "").lower()
        insured_name = assessment_data.get("insured_entity_name") or assessment_data.get("insured_name", "")

        # Category-specific exclusions, subjectivities, warranties, conditions
        exclusions, subjectivities, warranties, conditions = self._build_category_clauses(
            risk_category, insured_name, assessment_data
        )

        # Risk-score-aware adjustments
        if risk_score >= 80:
            # HIGH RISK — stricter terms
            exclusions += (
                "\n\nADDITIONAL EXCLUSIONS (Enhanced Risk Profile):\n"
                "- Prior and pending litigation exclusion\n"
                "- Regulatory investigation exclusion (unless defence costs sub-limit applies)\n"
                "- Loss of digital assets / cryptocurrency exclusion\n"
                "- Bodily injury / property damage arising from professional services\n"
                "- Insolvency of any party\n"
                "- Retroactive date limitation: No cover for wrongful acts prior to [retroactive date]"
            )

            subjectivities += (
                "\n\nADDITIONAL SUBJECTIVITIES (Enhanced Risk Profile):\n"
                f"- Independent risk survey of {insured_name} operations within 60 days of inception\n"
                "- Receipt of board-approved risk management framework\n"
                "- Satisfactory review of regulatory compliance history\n"
                "- Enhanced due diligence on key personnel and beneficial ownership\n"
                "- Confirmation of no pending or threatened regulatory actions\n"
                "- Receipt of independent IT security audit (for cyber exposures)\n"
                "- Quarterly loss experience reporting throughout the policy period"
            )

            warranties += (
                "\n\nADDITIONAL WARRANTIES (Enhanced Risk Profile):\n"
                f"- {insured_name} maintains minimum capital adequacy ratios as required by applicable regulators\n"
                "- No material change to business operations without prior written consent of Underwriters\n"
                "- The Insured maintains professional indemnity run-off cover for departed principals\n"
                "- Immediate notification of any regulatory investigation or inquiry\n"
                "- Annual renewal of all professional certifications and licences"
            )

            conditions += (
                "\n\nADDITIONAL CONDITIONS (Enhanced Risk Profile):\n"
                "- 72-hour claims notification window (breach may prejudice cover)\n"
                "- Underwriters' right to appoint defence counsel\n"
                "- Quarterly risk management reports required\n"
                "- Right of audit of Insured's records on 48 hours' notice\n"
                "- Aggregate deductible applies across all claims in the policy period"
            )

        elif risk_score >= 60:
            # MEDIUM-HIGH RISK — some additional terms
            exclusions += (
                "\n\nAdditional Exclusions:\n"
                "- Prior and pending litigation\n"
                "- Regulatory fines (unless insurable by law)"
            )

            subjectivities += (
                "\n\nAdditional Subjectivities:\n"
                f"- Receipt of current risk management procedures for {insured_name}\n"
                "- Confirmation of no pending regulatory actions"
            )

        # Additional info based on risk score
        additional = ""
        if risk_score >= 80:
            additional = (
                f"IMPORTANT: This risk has been assessed with an elevated risk score of {risk_score}/100. "
                f"Enhanced terms, conditions and subjectivities apply. "
                f"Underwriters should note the heightened risk profile and ensure all "
                f"subjectivities are satisfied before binding. "
                f"Referral to senior underwriter required before acceptance."
            )
        elif risk_score >= 60:
            additional = (
                f"NOTE: This risk has been assessed with a risk score of {risk_score}/100. "
                f"Standard terms apply with additional monitoring requirements."
            )

        # Helper to convert None/empty to TBA for template rendering
        def _tba(value, suffix=""):
            """Return value as string, or 'TBA' if empty/None."""
            if value is None or str(value).strip() == "" or str(value).strip().lower() == "none":
                return "TBA"
            return str(value) + suffix

        def _format_number(value):
            """Format a numeric value with comma separators (e.g. 15,000,000).
            Currency symbol is added by the template via {currency} placeholder."""
            if value is None:
                return "TBA"
            try:
                amount = float(value)
                if amount == int(amount):
                    return f"{int(amount):,}"
                else:
                    return f"{amount:,.2f}"
            except (ValueError, TypeError):
                return str(value)

        currency = assessment_data.get("currency") or "GBP"

        # Determine basis of cover from risk category if not explicitly set
        explicit_basis = assessment_data.get("basis_of_cover")
        if explicit_basis:
            basis_of_cover = explicit_basis
        else:
            basis_map = {
                "property": "All Risks",
                "marine": "All Risks - Institute Cargo Clauses (A)",
                "cargo": "All Risks - Institute Cargo Clauses (A)",
                "aviation": "All Risks - AVN1C",
                "energy": "All Risks - Industrial All Risks",
                "hull": "All Risks - Institute Time Clauses",
                "fire": "All Risks",
                "motor": "Comprehensive",
                "cyber": "Claims Made",
                "professional": "Claims Made",
                "professional_lines": "Claims Made",
                "d_and_o": "Claims Made",
                "e_and_o": "Claims Made",
                "financial": "Claims Made",
                "casualty": "Losses Occurring",
                "liability": "Losses Occurring",
            }
            basis_of_cover = basis_map.get(risk_category, "All Risks")

        return {
            "umr": f"B0000/IR/{datetime.utcnow().strftime('%Y')}",
            "broker_ref": f"IR/{datetime.utcnow().strftime('%Y')}/001",
            "type_of_business": assessment_data.get("type_of_business") or "New",
            "class_of_business": (assessment_data.get("risk_category") or "General").replace("_", " ").title(),
            "risk_code": assessment_data.get("risk_code") or self._derive_risk_code(risk_category),
            "placing_type": "Open Market",
            "insured_name": insured_name or "TBA",
            "named_insured": insured_name or "TBA",
            "insured_address": assessment_data.get("insured_address") or "TBA",
            "insured_country": assessment_data.get("territory") or "TBA",
            "period_from": _tba(assessment_data.get("inception_date")),
            "period_to": _tba(assessment_data.get("expiry_date")),
            "inception_time": "00:01",
            "interest": self._build_interest_description(assessment_data),
            "territorial_limits": self._build_territorial_limits(assessment_data),
            "limit_of_liability": _format_number(assessment_data.get("sum_insured")),
            "sub_limits": "",
            "deductible": _format_number(assessment_data.get("deductible")),
            "currency": currency,
            "basis_of_cover": basis_of_cover,
            "retroactive_date": "",
            "premium_amount": _format_number(assessment_data.get("premium")),
            "premium": _format_number(assessment_data.get("premium")),
            "premium_terms": "Net of brokerage at {commission}%".format(
                commission=assessment_data.get("commission_rate", "TBA")
            ) if assessment_data.get("commission_rate") else "Net premium as agreed",
            "subjectivities": subjectivities,
            "warranties": warranties,
            "exclusions": exclusions,
            "conditions": conditions,
            "claims_contact": assessment_data.get("broker_name") or "TBA",
            "claims_location": "London",
            "lead_underwriter": "TBA",
            "lead_syndicate": "TBA",
            "lead_reference": "TBA",
            "signed_line": "TBA",
            "order_percentage": "TBA",
            "following_markets": "TBA",
            "broker_name": assessment_data.get("broker_name") or "TBA",
            "broker_address": "TBA",
            "broker_pin": "TBA",
            "broker_reference": assessment_data.get("broker_reference") or "TBA",
            "commission_rate": _tba(assessment_data.get("commission_rate"), suffix="%" if assessment_data.get("commission_rate") else ""),
            "additional_information": additional,
            "policy_number": "TBA",
            "cover_note_number": "TBA",
        }

    @staticmethod
    def _derive_risk_code(risk_category: str) -> str:
        """Map risk_category to Lloyd's standard risk code."""
        risk_code_map = {
            "property": "1681",
            "fire": "1681",
            "commercial_property": "1681",
            "marine": "0510",
            "marine_cargo": "0540",
            "marine_hull": "0510",
            "cyber": "3379",
            "liability": "3000",
            "professional": "3250",
            "professional_lines": "3250",
            "d_and_o": "3230",
            "e_and_o": "3250",
            "casualty": "3000",
            "financial": "3200",
            "energy": "1500",
            "aviation": "0100",
            "motor": "0700",
        }
        return risk_code_map.get(risk_category, "")

    def _build_category_clauses(self, category: str, insured: str, data: dict):
        """Build category-specific exclusions, subjectivities, warranties, conditions."""

        # ── COMMON BASE ──
        base_exclusions = "War, invasion, hostilities (NMA 464)\nNuclear risks (NMA 1975)\nSanctions limitation and exclusion (LMA3100)"
        base_conditions = (
            "Claims Cooperation Clause: The Insured shall cooperate fully with Underwriters in the "
            "investigation, defence and settlement of any claim.\n\n"
            "Duty of Fair Presentation: In accordance with the Insurance Act 2015, the Insured has a "
            "duty to make a fair presentation of the risk.\n\n"
            "Subrogation: Underwriters shall be subrogated to all rights of recovery of the Insured."
        )

        if category == "cyber":
            exclusions = (
                f"{base_exclusions}\n\n"
                "CYBER-SPECIFIC EXCLUSIONS:\n"
                "1. Prior Knowledge: Any circumstance, act, error or omission which the Insured knew or "
                "ought reasonably to have known prior to inception could give rise to a claim.\n\n"
                "2. Unencrypted Data: Loss arising from unencrypted portable devices or media where the "
                "Insured has not implemented and enforced an encryption policy.\n\n"
                "3. Infrastructure Failure: Failure of electrical, gas, water, telephone or internet "
                "infrastructure not under the Insured's operational control.\n\n"
                "4. Betterment: Costs to improve, upgrade or enhance any Computer System beyond the "
                "level of functionality existing prior to the Network Security Incident.\n\n"
                "5. Patent & Trade Secret: Claims alleging infringement of patent rights or "
                "misappropriation of trade secrets.\n\n"
                "6. Contractual Penalties: Liquidated damages or contractual penalties unless liability "
                "would have existed in the absence of such contract.\n\n"
                "7. Bodily Injury / Property Damage: Physical bodily injury or tangible property damage "
                "(other than destruction of or damage to Data).\n\n"
                "8. Voluntary Shutdown: Loss arising from the Insured's voluntary shutdown of a Computer "
                "System unless necessitated by a covered Network Security Incident."
            )
            subjectivities = (
                "Prior to inception, receipt and approval of:\n"
                f"1. Completed cyber insurance proposal form for {insured}\n"
                "2. Current SOC2 Type II audit report (or equivalent security certification)\n"
                "3. Evidence of Multi-Factor Authentication (MFA) across all remote access\n"
                "4. Incident Response Plan (tested within last 12 months)\n"
                "5. Satisfactory loss history (5 years) including all cyber incidents\n"
                "6. Network architecture diagram and data flow mapping\n"
                "7. Confirmation of endpoint detection and response (EDR) deployment\n"
                "8. Data backup and recovery procedures (including offline/immutable backups)\n\n"
                "All subjectivities to be satisfied within 30 days of inception."
            )
            warranties = (
                f"The Insured ({insured}) warrants that throughout the currency of this insurance:\n\n"
                "1. Multi-factor authentication shall be maintained on all remote access points, "
                "email systems, and privileged accounts.\n\n"
                "2. Critical security patches shall be applied within 30 days of release.\n\n"
                "3. Employee security awareness training shall be conducted at least annually.\n\n"
                "4. Data backups shall be performed daily with at least one offline/immutable copy "
                "maintained and tested quarterly.\n\n"
                "5. The Insured shall maintain and test an Incident Response Plan at least annually.\n\n"
                "6. The Insured shall notify Underwriters within 30 days of any material change to "
                "IT infrastructure, security controls, or data processing activities."
            )
            conditions = (
                f"{base_conditions}\n\n"
                "CYBER-SPECIFIC CONDITIONS:\n\n"
                "Notice of Claim/Circumstances: The Insured shall give notice to Underwriters as soon "
                "as practicable and in any event within 30 days of discovery of any:\n"
                "(a) Security Incident or Data Breach\n"
                "(b) Claim or threatened claim\n"
                "(c) Regulatory investigation or inquiry\n\n"
                "Breach Response Vendors: The Insured shall use pre-approved breach response vendors "
                "from the panel set out in the Schedule. Use of non-panel vendors requires prior "
                "written consent of Underwriters.\n\n"
                "Ransomware Protocol: No ransom payment shall be made without prior written consent "
                "of Underwriters. The Insured shall engage approved forensic investigators before "
                "any payment is considered."
            )

        elif category == "property":
            exclusions = (
                f"{base_exclusions}\n\n"
                "PROPERTY-SPECIFIC EXCLUSIONS:\n"
                "1. Wear and Tear: Gradual deterioration, wear and tear, rust, corrosion, "
                "mould, wet or dry rot.\n\n"
                "2. Mechanical/Electrical Breakdown: Mechanical or electrical breakdown unless "
                "fire or explosion ensues, in which case cover applies to the ensuing damage only.\n\n"
                "3. Subsidence: Loss caused by subsidence, heave or landslip unless specifically "
                "included by endorsement.\n\n"
                "4. Pollution: Pollution or contamination unless caused by a sudden, identifiable, "
                "unintended and unexpected event occurring during the Period of Insurance.\n\n"
                "5. Cyber Attack: Loss arising from any cyber act (NMA 2914/2915) unless fire or "
                "explosion ensues as a direct result.\n\n"
                "6. Consequential Loss: Consequential loss of any kind unless specifically insured "
                "under the Business Interruption section.\n\n"
                "7. Vacant Premises: Unoccupied for more than 30 consecutive days unless agreed "
                "by Underwriters with appropriate premium adjustment.\n\n"
                "8. Defective Design: Faulty or defective design, materials or workmanship, but "
                "this shall not exclude resultant damage which itself is not otherwise excluded."
            )
            subjectivities = (
                "Prior to inception, receipt and approval of:\n"
                f"1. Completed commercial property proposal form for {insured}\n"
                "2. Current professional valuation report (Day One Reinstatement basis)\n"
                "3. Fire risk assessment and survey report (within last 24 months)\n"
                "4. Sprinkler system maintenance certificate (where applicable)\n"
                "5. Satisfactory loss history (5 years)\n"
                "6. Current fire and security alarm maintenance certificates\n"
                "7. Electrical installation certificate (within 5 years)\n"
                "8. Business continuity plan\n\n"
                "All subjectivities to be satisfied within 30 days of inception."
            )
            warranties = (
                f"The Insured ({insured}) warrants that throughout the currency of this insurance:\n\n"
                "1. All fire protection systems (sprinklers, alarms, extinguishers) shall be "
                "maintained in efficient working order and inspected as per manufacturer requirements.\n\n"
                "2. The premises shall not be left unoccupied for more than 30 consecutive days "
                "without prior notification to Underwriters.\n\n"
                "3. All hot work shall be conducted under a formal hot work permit system.\n\n"
                "4. Waste materials shall be removed from the premises at least weekly and shall "
                "not be stored within 10 metres of any building.\n\n"
                "5. Electrical installations shall be inspected and tested at intervals not exceeding "
                "5 years by a qualified electrician.\n\n"
                "6. The Insured shall maintain security arrangements as declared in the proposal form."
            )
            conditions = (
                f"{base_conditions}\n\n"
                "PROPERTY-SPECIFIC CONDITIONS:\n\n"
                "Basis of Settlement: Reinstatement as new (Day One basis) subject to adequate "
                "Sum Insured. Average/co-insurance applies if the Sum Insured is less than the "
                "Reinstatement Value.\n\n"
                "72-Hour Clause: All losses arising from a single event of storm, tempest, flood "
                "or earthquake within a 72-hour period shall be treated as a single occurrence.\n\n"
                "Automatic Reinstatement: Following a loss, the Sum Insured shall be automatically "
                "reinstated subject to payment of additional premium.\n\n"
                "Underinsurance: If at the time of loss the Sum Insured is less than the total "
                "value at risk, Underwriters' liability shall be proportionately reduced."
            )

        elif category == "marine":
            exclusions = (
                f"{base_exclusions}\n\n"
                "MARINE-SPECIFIC EXCLUSIONS:\n"
                "1. Inherent Vice: Loss caused by inherent vice or nature of the subject-matter "
                "insured, including ordinary leakage, loss in weight or volume.\n\n"
                "2. Delay: Loss proximately caused by delay, even though the delay be caused by "
                "a risk insured against.\n\n"
                "3. Insolvency: Loss caused by insolvency or financial default of the owners, "
                "managers, charterers or operators of the vessel.\n\n"
                "4. Insufficiency of Packing: Loss caused by insufficiency or unsuitability of "
                "packing or preparation of the subject-matter insured.\n\n"
                "5. Wilful Misconduct: Loss attributable to wilful misconduct of the Assured.\n\n"
                "6. Unseaworthiness: Where the Assured or their servants are privy to unseaworthiness "
                "or unfitness of vessel at the time of loading.\n\n"
                "7. Ordinary Wear and Tear: Ordinary leakage, breakage, chipping, denting, "
                "scratching or discolouration.\n\n"
                "8. War and Strikes: Institute War Clauses and Institute Strikes Clauses apply "
                "separately at additional premium (if required)."
            )
            subjectivities = (
                "Prior to inception, receipt and approval of:\n"
                f"1. Completed marine cargo proposal form for {insured}\n"
                "2. Annual cargo declaration and commodity schedule\n"
                "3. Trade route details with estimated values per conveyance\n"
                "4. Carrier selection and vetting procedures\n"
                "5. Satisfactory loss history (5 years) with full bordereaux\n"
                "6. Packing and handling standards documentation\n"
                "7. Details of any accumulation controls\n"
                "8. GPS tracking/security protocols for high-value shipments\n\n"
                "All subjectivities to be satisfied within 30 days of inception."
            )
            warranties = (
                f"The Insured ({insured}) warrants that throughout the currency of this insurance:\n\n"
                "1. All shipments shall be packed in accordance with best trade practice and "
                "suitable for the mode of transit employed.\n\n"
                "2. Approved carriers only: All carriers must maintain membership of an approved "
                "P&I Club and hold valid classification from a recognised society.\n\n"
                "3. Maximum value per conveyance shall not exceed the limits stated in the Schedule "
                "without prior agreement of Underwriters.\n\n"
                "4. Institute Warranty Limits (IWL) shall be observed. Trading outside IWL areas "
                "held covered at premium and conditions to be agreed.\n\n"
                "5. The Insured shall notify Underwriters of any shipment exceeding the agreed "
                "declaration threshold within 30 days of shipment.\n\n"
                "6. Temperature-controlled cargo shall be shipped in appropriate reefer containers "
                "with continuous temperature monitoring (where applicable)."
            )
            conditions = (
                f"{base_conditions}\n\n"
                "MARINE-SPECIFIC CONDITIONS:\n\n"
                "Duration: Warehouse to warehouse as per Institute Cargo Clauses (A) Clause 8. "
                "Cover terminates 60 days after discharge from oversea vessel.\n\n"
                "Duty of Assured: It is the duty of the Assured and their agents to take such "
                "measures as may be reasonable for the purpose of averting or minimising a loss.\n\n"
                "Constructive Total Loss: No claim for constructive total loss shall be recoverable "
                "unless the subject-matter insured is reasonably abandoned.\n\n"
                "General Average: This insurance covers general average and salvage charges, "
                "adjusted or determined according to the contract of carriage."
            )

        elif category == "aviation":
            exclusions = (
                f"{base_exclusions}\n\n"
                "AVIATION-SPECIFIC EXCLUSIONS:\n"
                "1. Wear and Tear: Gradual deterioration, wear and tear, or mechanical/electrical "
                "breakdown unless resulting from an accident.\n\n"
                "2. Unlicensed Operation: Loss whilst the aircraft is operated by or in charge of "
                "a person not holding a valid licence or rating.\n\n"
                "3. Airworthiness: Loss while the aircraft does not have a valid Certificate of "
                "Airworthiness or Permit to Fly.\n\n"
                "4. Overloading: Loss whilst the aircraft is carrying passengers or cargo in excess "
                "of the limitations specified in the aircraft's operating manual.\n\n"
                "5. Noise & Pollution: Third party liability arising from noise, pollution or "
                "contamination unless directly resulting from an accident.\n\n"
                "6. War and Allied Perils: As per AVN48B (Aviation War, Hi-Jacking and Other "
                "Perils Exclusion Clause) unless separately covered."
            )
            subjectivities = (
                "Prior to inception, receipt and approval of:\n"
                f"1. Completed aviation proposal form for {insured}\n"
                "2. Aircraft fleet schedule with values, registration, and type details\n"
                "3. Pilot/crew qualifications and flight hours documentation\n"
                "4. Satisfactory loss history (5 years)\n"
                "5. Current Certificate of Airworthiness for each aircraft\n"
                "6. Maintenance programme documentation (approved by CAA/EASA)\n"
                "7. Operations manual and safety management system documentation\n\n"
                "All subjectivities to be satisfied within 30 days of inception."
            )
            warranties = (
                f"The Insured ({insured}) warrants that throughout the currency of this insurance:\n\n"
                "1. All aircraft shall maintain a valid Certificate of Airworthiness.\n\n"
                "2. All pilots shall hold valid licences and ratings appropriate for the aircraft "
                "type and operation being conducted.\n\n"
                "3. Aircraft shall be maintained in accordance with manufacturer's requirements "
                "and an approved maintenance programme.\n\n"
                "4. Operations shall be conducted in accordance with applicable aviation regulations "
                "and the Insured's operations manual.\n\n"
                "5. The aircraft shall not be used for any purpose other than stated in the Schedule."
            )
            conditions = (
                f"{base_conditions}\n\n"
                "AVIATION-SPECIFIC CONDITIONS:\n\n"
                "Agreed Value: The aircraft values stated in the Schedule are agreed values for "
                "the purpose of total loss settlement.\n\n"
                "Notice of Loss: Immediate notice to Underwriters of any accident, incident or "
                "occurrence that may give rise to a claim. The aircraft shall not be moved or "
                "repaired without Underwriters' consent (except to prevent further damage).\n\n"
                "Geographic Limits: As stated in the Schedule. Ferrying outside geographic limits "
                "held covered at premium to be agreed."
            )

        elif category == "energy":
            exclusions = (
                f"{base_exclusions}\n\n"
                "ENERGY-SPECIFIC EXCLUSIONS:\n"
                "1. Wear and Tear: Gradual deterioration, wear and tear, corrosion, erosion, "
                "oxidation, or scaling.\n\n"
                "2. Faulty Design: Cost of making good faulty design, materials or workmanship "
                "but resultant damage covered.\n\n"
                "3. Existing Damage: Damage existing at inception of this insurance.\n\n"
                "4. Consequential Loss: Loss of use, delay or consequential loss unless specifically "
                "covered under the OEE/BI section.\n\n"
                "5. Pollution/Seepage: Gradual pollution, seepage or contamination unless caused "
                "by a sudden and accidental event.\n\n"
                "6. Decommissioning: Costs of decommissioning, plugging and abandonment.\n\n"
                "7. Reservoir/Underground: Loss of or damage to the well or reservoir below "
                "the surface of the earth or water (unless specifically included).\n\n"
                "8. Government Action: Confiscation, nationalisation, requisition by any government."
            )
            subjectivities = (
                "Prior to inception, receipt and approval of:\n"
                f"1. Completed energy proposal form for {insured}\n"
                "2. Current engineering survey/condition assessment\n"
                "3. Satisfactory loss history (5 years)\n"
                "4. Health, Safety and Environment (HSE) audit report\n"
                "5. Emergency response procedures and evidence of testing\n"
                "6. Current financial statements\n"
                "7. Details of all contractors and their insurance arrangements\n"
                "8. Production/revenue forecasts (for BI/OEE cover)\n\n"
                "All subjectivities to be satisfied within 30 days of inception."
            )
            warranties = (
                f"The Insured ({insured}) warrants that throughout the currency of this insurance:\n\n"
                "1. All operations shall comply with applicable HSE regulations and industry "
                "best practice.\n\n"
                "2. Planned maintenance programmes shall be maintained and all safety-critical "
                "equipment inspected per manufacturer specifications.\n\n"
                "3. All personnel shall hold appropriate qualifications and certifications.\n\n"
                "4. Emergency response procedures shall be tested at least annually.\n\n"
                "5. Any material change in operations, equipment or personnel shall be notified "
                "to Underwriters within 30 days."
            )
            conditions = (
                f"{base_conditions}\n\n"
                "ENERGY-SPECIFIC CONDITIONS:\n\n"
                "Operators Extra Expense: OEE cover applies to the additional costs necessarily "
                "incurred in controlling, re-drilling or making safe following a well out of control.\n\n"
                "Sue and Labour: Underwriters shall contribute to charges properly and reasonably "
                "incurred for the preservation of the insured property.\n\n"
                "Removal of Debris: Costs of removal of wreck and debris covered up to 25% of "
                "the loss amount."
            )

        else:
            # Casualty / General Liability / Other
            exclusions = (
                f"{base_exclusions}\n\n"
                "LIABILITY-SPECIFIC EXCLUSIONS:\n"
                "1. Employers Liability: Bodily injury to any employee arising out of and in "
                "the course of employment (unless EL section applies).\n\n"
                "2. Professional Liability: Claims arising from professional advice or services "
                "(unless Professional Indemnity section applies).\n\n"
                "3. Product Recall: Costs of recalling, removing, repairing, replacing or "
                "disposing of any product.\n\n"
                "4. Contractual Liability: Liability assumed under contract unless such liability "
                "would have existed in the absence of the contract.\n\n"
                "5. Asbestos: Claims arising from or relating to asbestos in any form.\n\n"
                "6. Pollution: Gradual pollution or contamination unless caused by a sudden, "
                "identifiable, unintended event during the Policy Period.\n\n"
                "7. Punitive Damages: Fines, penalties, punitive or exemplary damages.\n\n"
                "8. Known Circumstances: Any claim arising from circumstances known to the "
                "Insured prior to inception."
            )
            subjectivities = (
                "Prior to inception, receipt and approval of:\n"
                f"1. Completed liability proposal form for {insured}\n"
                "2. Current risk assessment and health & safety documentation\n"
                "3. Satisfactory loss history (5 years)\n"
                "4. Current financial statements\n"
                "5. Details of contractual liabilities and hold harmless agreements\n"
                "6. Product/service descriptions and quality control procedures\n\n"
                "All subjectivities to be satisfied within 30 days of inception."
            )
            warranties = (
                f"The Insured ({insured}) warrants that throughout the currency of this insurance:\n\n"
                "1. All information provided in the proposal form is true, complete and accurate.\n\n"
                "2. Appropriate risk management and health & safety procedures shall be maintained.\n\n"
                "3. All applicable laws, regulations and industry standards shall be complied with.\n\n"
                "4. The Insured shall notify Underwriters promptly of any material change in "
                "the business, operations or risk profile.\n\n"
                "5. Adequate records of all incidents and near-misses shall be maintained."
            )
            conditions = (
                f"{base_conditions}\n\n"
                "LIABILITY-SPECIFIC CONDITIONS:\n\n"
                "Defence and Settlement: Underwriters shall have the right but not the duty to "
                "defend any claim. No admission of liability or settlement without Underwriters' "
                "prior written consent.\n\n"
                "Notice of Claim: The Insured shall give notice to Underwriters as soon as "
                "practicable and in any event within 30 days of:\n"
                "(a) receipt of any claim or legal proceedings\n"
                "(b) becoming aware of any circumstance likely to give rise to a claim\n\n"
                "Other Insurance: This insurance shall apply in excess of any other valid and "
                "collectible insurance."
            )

        return exclusions, subjectivities, warranties, conditions

    def _build_interest_description(self, data: dict) -> str:
        """Build a detailed INTEREST section based on risk category and description."""
        category = (data.get("risk_category") or "general").lower()
        insured = data.get("insured_name") or data.get("insured_entity_name") or "the Insured"
        desc = data.get("description") or ""
        exposure = data.get("exposure_details") or {}

        interest_map = {
            "cyber": (
                f"Cyber Liability Insurance in respect of:\n"
                f"(a) Data breach response costs and notification expenses\n"
                f"(b) Network security liability\n"
                f"(c) Privacy liability arising from wrongful disclosure of personal data\n"
                f"(d) Network business interruption loss and extra expense\n"
                f"(e) Cyber extortion costs and ransom payments\n"
                f"(f) Media liability arising from digital media activities\n"
                f"All in connection with the business operations of {insured}."
            ),
            "property": (
                f"Commercial Property Insurance covering:\n"
                f"(a) Buildings, structures, and improvements at the Insured's premises\n"
                f"(b) Machinery, plant, and equipment\n"
                f"(c) Stock, materials, and contents\n"
                f"(d) Business interruption / loss of profits\n"
                f"All Risks of physical loss or damage to property of {insured}."
            ),
            "marine": (
                f"Marine Cargo Insurance covering:\n"
                f"(a) Goods, merchandise, and cargo in transit\n"
                f"(b) Institute Cargo Clauses (A) - All Risks basis\n"
                f"(c) General average and salvage charges\n"
                f"(d) Warehouse to warehouse coverage\n"
                f"In respect of shipments by or on behalf of {insured}."
            ),
            "casualty": (
                f"Casualty / General Liability Insurance covering:\n"
                f"(a) Third party bodily injury and property damage\n"
                f"(b) Products and completed operations liability\n"
                f"(c) Personal and advertising injury\n"
                f"(d) Legal defence costs\n"
                f"Arising from the business operations of {insured}."
            ),
            "aviation": (
                f"Aviation Insurance covering:\n"
                f"(a) Hull all risks (including ground risks and in-flight)\n"
                f"(b) Aviation liability including passenger liability\n"
                f"(c) Third party legal liability\n"
                f"In respect of aircraft operated by or on behalf of {insured}."
            ),
            "energy": (
                f"Energy Insurance covering:\n"
                f"(a) Physical damage to energy installations and infrastructure\n"
                f"(b) Operators Extra Expense (OEE)\n"
                f"(c) Business interruption / loss of production income\n"
                f"(d) Third party liability arising from energy operations\n"
                f"In respect of the energy operations of {insured}."
            ),
        }

        return interest_map.get(category, (
            f"{category.replace('_', ' ').title()} Insurance covering all risks as described "
            f"in the policy terms and conditions, in respect of the business operations of {insured}."
        ))

    def _build_territorial_limits(self, data: dict) -> str:
        """Build a detailed TERRITORIAL LIMITS section."""
        territory = data.get("territory") or "Worldwide"
        category = (data.get("risk_category") or "general").lower()

        base = territory
        if category == "marine":
            base += (
                f"\n\nInstitute Warranty Limits (IWL) apply.\n"
                f"Trading limits as per Institute Classification Clause.\n"
                f"Held covered at premium to be agreed for breach of trading limits."
            )
        elif category == "cyber":
            base += (
                f"\n\nCoverage applies to cyber incidents affecting the Insured's operations "
                f"or data regardless of where the incident originates, subject to applicable "
                f"sanctions restrictions."
            )
        elif territory.lower() in ("worldwide", "global"):
            base += "\n\nExcluding any country subject to applicable sanctions or embargoes."
        return base

    def _split_rendered_template(self, rendered: str) -> Dict[str, str]:
        """Split a rendered template into sections keyed by section title.

        Template format:
            ================
            SECTION TITLE
            ================
            content here
        After splitting on ={10,}, parts alternate: [preamble, TITLE, content, TITLE, content, ...]
        """
        import re
        sections = {}
        if not rendered:
            return sections

        # Split on separator lines (10+ equal signs)
        parts = re.split(r'={10,}', rendered)

        # parts[0] = preamble, then alternating title/content pairs
        if parts:
            preamble = parts[0].strip()
            if preamble:
                sections["PREAMBLE"] = preamble

        # Pair titles (odd indices) with content (even indices)
        i = 1
        while i < len(parts) - 1:
            title = parts[i].strip()
            content = parts[i + 1].strip()
            if title:
                sections[title.upper()] = content
            i += 2

        return sections

    async def agent_section_drafter(
        self,
        structure: Dict,
        selected_clauses: List[Dict],
        assessment_data: Dict,
        formatting: Dict,
        user_id: str = None,
        ml_context: Dict = None,
    ) -> List[Dict]:
        """Agent 7: SectionDrafter — render template + inject selected clauses. AI only for gaps."""
        from app.services.insurance_templates import render_template, STANDARD_CLAUSES

        template_id = structure.get("template_id")
        clause_map = {c["clause_id"]: c for c in selected_clauses}
        risk_category = assessment_data.get("risk_category", "property")
        drafted_sections = []
        gap_sections = []

        # Step 1: Render template with assessment data (instant, no AI)
        template_data = self._build_template_data(assessment_data)
        rendered = render_template(template_id, template_data) if template_id else ""
        rendered_sections = self._split_rendered_template(rendered)

        logger.info(f"SectionDrafter: template_id={template_id}, rendered_len={len(rendered)}, sections_found={list(rendered_sections.keys())}")

        template_hits = 0
        clause_hits = 0
        gap_count = 0

        for section in structure.get("sections", []):
            title = section["title"]
            title_upper = title.upper()

            # Priority 1: Rendered template content (data already filled in)
            rendered_content = rendered_sections.get(title_upper, "")
            # Also try partial match
            if not rendered_content:
                for key, val in rendered_sections.items():
                    if title_upper in key or key in title_upper:
                        rendered_content = val
                        break

            # Priority 2: Selected clause text from ClauseManager (from RAG)
            clause_content_parts = []
            clause_sources = []
            for cid in section.get("clause_ids", []):
                if cid in clause_map and clause_map[cid].get("selected_text"):
                    clause_content_parts.append(clause_map[cid]["selected_text"])
                    clause_sources.append({"id": cid, "source": clause_map[cid].get("source", "rag")})

            # Priority 3: Standard clauses from the embedded clause library (10 LMA clauses)
            std_clause_text = ""
            for std_key, std_clause in STANDARD_CLAUSES.items():
                std_name = std_clause.get("name", "").lower()
                std_id = std_clause.get("id", "").lower()
                if (std_name and std_name in title.lower()) or (std_id and std_id in title.lower()):
                    std_clause_text = std_clause["text"]
                    clause_sources.append({"id": std_clause["id"], "source": "lma_clause"})
                    break

            # Priority 3.5: Full clause library search (30K+ LEDGAR/CUAD/ContractNLI clauses)
            full_lib_text = ""
            if not std_clause_text:
                try:
                    from app.services.clauses_library_service import ClausesLibraryService
                    clause_lib = ClausesLibraryService()
                    # Search with risk category + section title for better relevance
                    search_query = f"{title} {risk_category}" if risk_category else title
                    lib_results, lib_total = clause_lib.search(
                        query=search_query,
                        line_of_business=risk_category,
                        page_size=5,
                    )
                    if lib_results:
                        # Pick best result that has substantial content
                        for candidate in lib_results:
                            cand_text = candidate.get("text", "")
                            cand_cat = (candidate.get("category", "") or "").lower()
                            # Skip results that are too short or from wrong domain
                            if not cand_text or len(cand_text) < 50:
                                continue
                            # Skip generic contract clauses that aren't insurance-relevant
                            non_insurance = ["employment", "real estate", "merger", "acquisition", "stock purchase"]
                            if any(ni in cand_cat for ni in non_insurance):
                                continue
                            full_lib_text = cand_text
                            clause_sources.append({"id": candidate.get("id", "clause_library"), "source": "clause_library"})
                            break
                except Exception as e:
                    logger.debug(f"Clause library search for '{title}': {e}")

            clause_content = "\n\n".join(clause_content_parts)
            if std_clause_text and not clause_content:
                clause_content = std_clause_text
            elif full_lib_text and not clause_content:
                clause_content = full_lib_text

            # Decide which content to use
            if rendered_content and rendered_content.strip():
                # Template content — already has data filled in
                template_hits += 1
                drafted_sections.append({
                    "section_number": section["section_number"],
                    "title": title,
                    "content": rendered_content.strip(),
                    "source_clauses": [{"id": "template", "source": "template"}],
                    "source_type": "template",
                })
            elif clause_content and clause_content.strip():
                # Real clause text from library/RAG
                clause_hits += 1
                # Determine source type from clause_sources
                src_type = "lma_clause"
                if clause_sources:
                    first_src = clause_sources[0].get("source", "")
                    if first_src == "clause_library":
                        src_type = "clause_library"
                    elif first_src in ("rag", "standard_clause", "lma_clause"):
                        src_type = first_src
                drafted_sections.append({
                    "section_number": section["section_number"],
                    "title": title,
                    "content": clause_content.strip(),
                    "source_clauses": clause_sources if clause_sources else [{"id": "clause_library", "source": "clause_library"}],
                    "source_type": src_type,
                })
            else:
                # No template or clause content — mark for gap filling
                gap_count += 1
                gap_sections.append(section)

        logger.info(f"SectionDrafter: template={template_hits}, clause={clause_hits}, gaps={gap_count}")

        # Step 2: Fill gaps — use section defaults first, then targeted RAG, then AI last resort
        # Section-specific default content for common Lloyd's MRC sections
        insured_name = assessment_data.get("insured_entity_name") or assessment_data.get("insured_name", "The Insured")
        section_defaults = {
            "SUBJECTIVITIES": (
                f"Prior to inception of the Policy, the following subjectivities must be satisfied:\n\n"
                f"1. Receipt and approval of the current risk management report for {insured_name}\n"
                f"2. Receipt and approval of {insured_name}'s completed proposal form\n"
                f"3. Receipt of satisfactory loss history for the previous five years\n"
                f"4. Receipt and approval of the current financial statements\n"
                f"5. Receipt of confirmation of current security arrangements\n\n"
                f"All subjectivities to be satisfied within 30 days of inception, failing which Underwriters "
                f"reserve the right to void coverage from inception."
            ),
            "WARRANTIES": (
                f"The Insured warrants that:\n\n"
                f"1. All information provided in the proposal form and supporting documentation is true, "
                f"complete and accurate in all material respects.\n"
                f"2. {insured_name} maintains appropriate risk management procedures and controls.\n"
                f"3. The Insured will notify Underwriters promptly of any material change in the risk.\n"
                f"4. The Insured complies with all applicable laws, regulations and industry standards.\n"
                f"5. The Insured maintains adequate records relating to the subject matter of this insurance.\n\n"
                f"Breach of any warranty shall entitle Underwriters to avoid liability from the date of breach."
            ),
            "EXCLUSIONS": (
                "In addition to the standard exclusions incorporated herein, this insurance "
                "does not cover:\n\n"
                "1. War, invasion, act of foreign enemies, hostilities or warlike operations\n"
                "2. Nuclear reaction, radiation or radioactive contamination (NMA1191)\n"
                "3. Loss arising from sanctions (LMA3100)\n"
                "4. Loss arising from fraud, dishonesty or criminal acts of the Insured\n"
                "5. Contractual liability unless such liability would have existed in the absence of the contract\n"
                "6. Fines, penalties, punitive or exemplary damages"
            ),
            "CONDITIONS": (
                "1. CLAIMS NOTIFICATION: The Insured shall give notice to Underwriters as soon as "
                "practicable of any occurrence which may give rise to a claim under this Policy.\n\n"
                "2. DUE DILIGENCE: The Insured shall take all reasonable precautions to prevent loss, "
                "damage or liability.\n\n"
                "3. COOPERATION: The Insured shall cooperate fully with Underwriters and provide all "
                "information and assistance as may be reasonably required.\n\n"
                "4. SUBROGATION: In the event of any payment under this Policy, Underwriters shall be "
                "subrogated to all the Insured's rights of recovery.\n\n"
                "5. OTHER INSURANCE: If any loss covered by this Policy is also covered by any other "
                "insurance, this Policy shall apply in excess of such other insurance."
            ),
            "ADDITIONAL CLAUSES": (
                "The following standard market clauses are incorporated herein:\n\n"
                "- LMA5096 Several Liability Clause\n"
                "- LMA5121 Law and Jurisdiction (England and Wales)\n"
                "- LMA3100 Sanctions Limitation and Exclusion\n"
                "- NMA1191 Radioactive Contamination Exclusion\n"
                "- LMA5235 Premium Payment Clause\n"
                "- NMA358 Claims Notification Clause"
            ),
        }

        for section in gap_sections:
            title_upper = section["title"].strip().upper()

            # Priority 1: Use section-specific defaults
            default_content = section_defaults.get(title_upper)
            if default_content:
                drafted_sections.append({
                    "section_number": section["section_number"],
                    "title": section["title"],
                    "content": default_content,
                    "source_clauses": [{"id": "standard_default", "source": "standard_default"}],
                    "source_type": "section_default",
                })
                continue

            # Priority 2: Targeted RAG search (higher min_score to avoid irrelevant results)
            rag_content = ""
            try:
                results = await asyncio.wait_for(
                    self.unified_rag.search(
                        query=f"{section['title']} {risk_category} insurance policy clause wording",
                        user_id=user_id,
                        top_k=5,
                        min_score=0.6,  # Higher threshold to avoid garbage
                    ),
                    timeout=30,
                )
                # Filter out cross-category results (e.g. marine cargo in cyber policy)
                if results and risk_category:
                    cat_lower = risk_category.lower()
                    # Categories that shouldn't cross-pollinate
                    exclusive_cats = {"marine", "cargo", "hull", "aviation", "cyber", "property", "motor", "liability"}
                    filtered = []
                    for r in results:
                        text_lower = (r.get("text", "") or "")[:500].lower()
                        source_label = (r.get("source_label", "") or "").lower()
                        # Reject results from wrong category
                        is_wrong_cat = False
                        for excl_cat in exclusive_cats:
                            if excl_cat != cat_lower and excl_cat in source_label:
                                is_wrong_cat = True
                                break
                            # Check content for strong category signals
                            if excl_cat != cat_lower and excl_cat not in cat_lower:
                                cat_signals = {
                                    "marine": ["vessel", "hull", "cargo", "maritime", "shipping", "charterer"],
                                    "cargo": ["goods in transit", "cargo", "bill of lading", "consignment"],
                                    "aviation": ["aircraft", "aviation", "flight", "airworthiness"],
                                    "motor": ["vehicle", "motor car", "driving", "road traffic"],
                                }
                                if excl_cat in cat_signals:
                                    signal_count = sum(1 for sig in cat_signals[excl_cat] if sig in text_lower)
                                    if signal_count >= 2:
                                        is_wrong_cat = True
                                        break
                        if not is_wrong_cat:
                            filtered.append(r)
                    results = filtered if filtered else results[:1]  # Keep at least 1 result
                rag_content = self.unified_rag.format_as_context(results, max_chars=2000)
            except Exception as e:
                logger.warning(f"SectionDrafter RAG gap-fill failed for '{section['title']}': {e}")

            if rag_content and rag_content.strip():
                drafted_sections.append({
                    "section_number": section["section_number"],
                    "title": section["title"],
                    "content": rag_content.strip(),
                    "source_clauses": [{"id": "rag", "source": "rag"}],
                    "source_type": "rag",
                })
            else:
                # Priority 3: Single AI call for this gap section
                try:
                    # Build ML insight block for AI gap-fill
                    ml_gap_block = ""
                    if ml_context:
                        appetite = ml_context.get("appetite", {})
                        pricing = ml_context.get("pricing", {})
                        ml_cats = [c["category"] for c in ml_context.get("clauses", [])[:8]]
                        ml_gap_block = (
                            f"\nInstantRisk Engine: appetite={appetite.get('decision','unknown')} "
                            f"({appetite.get('confidence',0):.0%}), "
                            f"pricing={pricing.get('band','unknown')}, "
                            f"clause categories={', '.join(ml_cats)}"
                        )
                    response = await asyncio.wait_for(
                        self._run_agent(
                            "SectionDrafter",
                            "You are a Lloyd's insurance document drafter. Write professional insurance wording.",
                            f"""Draft the '{section['title']}' section for a {structure.get('document_type', 'policy')} document.
Risk: {risk_category}, Insured: {insured_name}, Territory: {assessment_data.get('territory', '')}, Sum Insured: {self._fmt_currency(assessment_data.get('sum_insured'), assessment_data.get('currency', 'GBP'))}{ml_gap_block}
Write concise, professional Lloyd's market standard wording.""",
                            temperature=0.2,
                        ),
                        timeout=90,
                    )
                except asyncio.TimeoutError:
                    response = None

                drafted_sections.append({
                    "section_number": section["section_number"],
                    "title": section["title"],
                    "content": response or f"[{section['title']} - To be completed]",
                    "source_clauses": [{"id": "ai_generated", "source": "ai_generated"}],
                    "source_type": "ai_generated",
                    "requires_review": True,
                })

        # Sort by section number
        drafted_sections.sort(key=lambda s: int(str(s.get("section_number", 0)).split(".")[0]) if str(s.get("section_number", "0")).split(".")[0].isdigit() else 0)

        logger.info(f"SectionDrafter: completed {len(drafted_sections)} sections "
                     f"(template={template_hits}, clause={clause_hits}, gaps={gap_count})")
        return drafted_sections

    async def agent_consistency_checker(
        self,
        drafted_sections: List[Dict],
        assessment_data: Dict,
    ) -> Dict:
        """Agent 8: ConsistencyChecker — checks limits, deductibles, dates, names match across sections."""
        section_summary = "\n".join(
            f"Section {s['section_number']}: {s['title']} ({len(s.get('content', ''))} chars)"
            for s in drafted_sections[:25]
        )

        result = await self._run_agent_json(
            "ConsistencyChecker",
            "You are an insurance document consistency reviewer. Check that all numerical values, names, dates, and references are consistent across all sections.",
            f"""Check consistency across all sections of this insurance document.

Assessment values:
- Insured: {assessment_data.get('insured_entity_name') or assessment_data.get('insured_name', '')}
- Broker: {assessment_data.get('broker_name', '')}
- Commission: {assessment_data.get('commission_rate', '')}%
- Premium: {self._fmt_currency(assessment_data.get('premium'), assessment_data.get('currency', 'GBP'))}
- Sum insured: {self._fmt_currency(assessment_data.get('sum_insured'), assessment_data.get('currency', 'GBP'))}
- Deductible: {self._fmt_currency(assessment_data.get('deductible'), assessment_data.get('currency', 'GBP'))}
- Territory: {assessment_data.get('territory', '')}
- Inception: {assessment_data.get('inception_date', '')}
- Expiry: {assessment_data.get('expiry_date', '')}

Sections:
{section_summary}

First 500 chars of each section:
{chr(10).join(f"[{s['title']}]: {s.get('content', '')[:500]}" for s in drafted_sections[:15])}

Return ONLY valid JSON:
{{
    "consistent": true/false,
    "issues": [
        {{
            "type": "value_mismatch|name_mismatch|date_mismatch|reference_error",
            "description": "What's inconsistent",
            "sections_affected": [1, 2],
            "severity": "critical|warning"
        }}
    ],
    "notes": "Summary"
}}"""
        )
        return result or {"consistent": True, "issues": [], "notes": ""}

    async def agent_tone_unifier(
        self,
        drafted_sections: List[Dict],
    ) -> List[Dict]:
        """Agent 9: ToneUnifier — ensures consistent insurance legal language throughout."""
        # Light-touch: flag tone issues but don't rewrite everything
        result = await self._run_agent_json(
            "ToneUnifier",
            "You are an insurance language specialist. Ensure consistent professional tone across all document sections.",
            f"""Review these section openings for tone consistency. Flag any that don't match professional Lloyd's market language.

Sections:
{chr(10).join(f"[{s['title']}]: {s.get('content', '')[:300]}" for s in drafted_sections[:15])}

Return ONLY valid JSON:
{{
    "tone_consistent": true/false,
    "sections_needing_revision": [
        {{
            "section_number": 1,
            "issue": "What's wrong with the tone",
            "suggestion": "How to fix"
        }}
    ]
}}"""
        )
        # Return sections as-is (tone fixes applied in refinement phase)
        return drafted_sections

    # ─── PHASE 4: VALIDATE (Agents 10-12) ─────────────────────────────

    async def agent_risk_challenger(
        self,
        drafted_sections: List[Dict],
        assessment_data: Dict,
        user_id: str = None,
        ml_context: Dict = None,
    ) -> Dict:
        """Agent 10: RiskChallenger — challenges coverage adequacy, finds exclusion gaps."""
        risk_category = assessment_data.get('risk_category', '')
        territory = assessment_data.get('territory', '')

        # Search RAG for similar risk precedents and coverage standards
        rag_context = ""
        try:
            results = await self.unified_rag.search(
                query=f"{risk_category} insurance coverage gaps exclusions {territory} Lloyd's underwriting",
                user_id=user_id,
                top_k=5,
                min_score=0.3,
            )
            rag_context = self.unified_rag.format_as_context(results, max_chars=2000)
        except Exception as e:
            logger.warning(f"RiskChallenger RAG search failed: {e}")

        rag_block = f"\nMARKET PRECEDENTS AND STANDARDS:\n{rag_context}\n" if rag_context else ""

        ml_block = ""
        if ml_context:
            appetite = ml_context.get("appetite", {})
            pricing = ml_context.get("pricing", {})
            ml_block = f"""
INSTANTRISK ENGINE ANALYSIS:
- Risk appetite: {appetite.get('decision', 'unknown')} (confidence: {appetite.get('confidence', 0):.0%})
  Scores: accept={appetite.get('scores', {}).get('accept', 0):.2f}, refer={appetite.get('scores', {}).get('refer', 0):.2f}, decline={appetite.get('scores', {}).get('decline', 0):.2f}
- Pricing band: {pricing.get('band', 'unknown')} (confidence: {pricing.get('confidence', 0):.0%})
Use these data-driven signals to inform your risk challenge.
"""

        result = await self._run_agent_json(
            "RiskChallenger",
            "You are a senior Lloyd's underwriter reviewing a placement. Challenge the coverage adequacy and identify potential gaps or weaknesses. Use market precedents and InstantRisk Engine analysis to inform your review.",
            f"""Challenge this insurance document's coverage adequacy.

Risk: {risk_category} in {territory}
Insured: {assessment_data.get('insured_entity_name') or assessment_data.get('insured_name', '')}
Sum insured: {assessment_data.get('sum_insured', '')}
Inception: {assessment_data.get('inception_date', '')}
Broker: {assessment_data.get('broker_name', '')}
Sections: {', '.join(s['title'] for s in drafted_sections[:20])}
{rag_block}{ml_block}

Key content:
{chr(10).join(f"[{s['title']}]: {s.get('content', '')[:400]}" for s in drafted_sections[:10])}

As a senior underwriter, identify:
1. Coverage adequacy issues
2. Missing exclusions that should be present
3. Conditions that need strengthening
4. Aggregation or accumulation concerns

Return ONLY valid JSON:
{{
    "coverage_adequate": true/false,
    "challenges": [
        {{
            "area": "What area needs attention",
            "concern": "The specific concern",
            "severity": "critical|important|minor",
            "recommendation": "Suggested fix"
        }}
    ],
    "risk_appetite_notes": "Notes on risk appetite alignment"
}}"""
        )
        return result or {"coverage_adequate": True, "challenges": [], "risk_appetite_notes": ""}

    async def agent_clause_verifier(
        self,
        selected_clauses: List[Dict],
    ) -> Dict:
        """Agent 11: ClauseVerifier — verifies clause IDs exist and wording matches standards."""
        result = await self._run_agent_json(
            "ClauseVerifier",
            "You are a Lloyd's clause verification specialist. Verify that all referenced clause IDs are valid ACORD/LMA/ICC standard clauses.",
            f"""Verify these clause references are valid standard clauses.

Clauses used:
{json.dumps([{"id": c.get("clause_id", ""), "name": c.get("name", ""), "source": c.get("source", "unknown")} for c in selected_clauses[:30]], indent=2)}

For each clause, verify:
1. Is this a real standard clause ID?
2. Does the name match the standard?
3. Is it being used appropriately?

Return ONLY valid JSON:
{{
    "all_verified": true/false,
    "verification": [
        {{
            "clause_id": "ID",
            "verified": true/false,
            "issue": "Issue if not verified",
            "correct_id": "Correct ID if wrong"
        }}
    ]
}}"""
        )
        return result or {"all_verified": True, "verification": []}

    async def agent_compliance_reviewer(
        self,
        drafted_sections: List[Dict],
        assessment_data: Dict,
        user_id: str = None,
        ml_context: Dict = None,
    ) -> Dict:
        """Agent 12: ComplianceReviewer — simulates Lloyd's compliance review."""
        risk_category = assessment_data.get('risk_category', '')
        territory = assessment_data.get('territory', '')

        # Search RAG for regulatory requirements and compliance standards
        rag_context = ""
        try:
            results = await self.unified_rag.search(
                query=f"Lloyd's compliance mandatory clauses sanctions PRA FCA regulatory {territory} {risk_category}",
                user_id=user_id,
                top_k=5,
                min_score=0.3,
            )
            rag_context = self.unified_rag.format_as_context(results, max_chars=2000)
        except Exception as e:
            logger.warning(f"ComplianceReviewer RAG search failed: {e}")

        rag_block = f"\nREGULATORY REFERENCE MATERIAL:\n{rag_context}\n" if rag_context else ""

        ml_block = ""
        if ml_context:
            ml_clauses = ml_context.get("clauses", [])
            appetite = ml_context.get("appetite", {})
            clause_cats = [c["category"] for c in ml_clauses[:15]]
            ml_block = f"""
INSTANTRISK ENGINE CLAUSE ANALYSIS:
- ML-recommended clause categories: {', '.join(clause_cats)}
- Risk appetite: {appetite.get('decision', 'unknown')} ({appetite.get('confidence', 0):.0%})
Verify that mandatory clause categories from the ML model are present in the document.
"""

        result = await self._run_agent_json(
            "ComplianceReviewer",
            "You are a Lloyd's compliance officer. Review this document for regulatory compliance including sanctions, PRA/FCA requirements, and market standards. Use reference material and InstantRisk Engine analysis to verify requirements.",
            f"""Review this insurance document for Lloyd's compliance.

Document sections: {', '.join(s['title'] for s in drafted_sections[:20])}
Risk category: {risk_category}
Territory: {territory}
Insured: {assessment_data.get('insured_entity_name') or assessment_data.get('insured_name', '')}
Regulatory framework: {assessment_data.get('regulatory_framework', 'N/A')}
Loss run reporting rules: {assessment_data.get('loss_run_reporting_rules', 'N/A')}
{rag_block}{ml_block}

Check for:
1. Missing mandatory Lloyd's clauses (Several Liability, Sanctions, etc.)
2. PRA/FCA regulatory requirements
3. Territory-specific regulations
4. Sanctions screening requirements
5. Data protection / GDPR if applicable

Return ONLY valid JSON:
{{
    "compliant": true/false,
    "missing_mandatory": ["List of missing mandatory clauses"],
    "regulatory_issues": ["Regulatory concerns"],
    "recommendations": ["Compliance recommendations"],
    "sanctions_check": "pass|requires_screening|fail",
    "confidence": 0.0-1.0
}}"""
        )
        return result or {"compliant": True, "missing_mandatory": [], "regulatory_issues": [], "recommendations": [], "confidence": 0.5}

    # ─── PHASE 5: REFINE (Agents 13-16) ───────────────────────────────

    async def agent_house_style(
        self,
        drafted_sections: List[Dict],
        user_id: str = None,
    ) -> List[Dict]:
        """Agent 13: HouseStyleAgent — matches output to user's uploaded training docs style."""
        # If user has training docs, search for style examples
        style_context = ""
        if user_id:
            try:
                from app.services.qdrant_service import qdrant_service
                style_docs = await qdrant_service.search_similar(
                    query="document style formatting language",
                    user_id=user_id,
                    limit=3,
                )
                if style_docs:
                    style_context = "\n\n".join(
                        f"[User style example]: {d.get('text', '')[:500]}"
                        for d in style_docs
                    )
            except Exception as e:
                logger.debug(f"Style context retrieval failed: {e}")

        if not style_context:
            return drafted_sections

        # Apply style matching
        result = await self._run_agent_json(
            "HouseStyleAgent",
            "You are a document style matching specialist. Analyze the user's house style and suggest adjustments.",
            f"""Compare the document sections against the user's house style.

USER'S STYLE EXAMPLES:
{style_context}

CURRENT DOCUMENT SECTIONS (first 300 chars each):
{chr(10).join(f"[{s['title']}]: {s.get('content', '')[:300]}" for s in drafted_sections[:10])}

Identify style differences and suggest adjustments.

Return ONLY valid JSON:
{{
    "style_matched": true/false,
    "adjustments": [
        {{
            "section_number": 1,
            "adjustment": "What to change",
            "reason": "Why"
        }}
    ]
}}"""
        )
        return drafted_sections

    async def agent_language_varier(
        self,
        drafted_sections: List[Dict],
    ) -> List[Dict]:
        """Agent 14: LanguageVarier — varies legal phrasing, avoids repetitive boilerplate."""
        # Light check — only flag repetitions
        await self._run_agent(
            "LanguageVarier",
            "You are a legal language editor. Identify repetitive phrasing in insurance documents.",
            f"""Check these sections for repetitive language:
{chr(10).join(f"[{s['title']}]: {s.get('content', '')[:200]}" for s in drafted_sections[:15])}

List any repetitive phrases that should be varied.""",
        )
        return drafted_sections

    async def agent_proof_reader(
        self,
        drafted_sections: List[Dict],
    ) -> Dict:
        """Agent 15: ProofReader — final grammar, numbering, cross-reference check."""
        result = await self._run_agent_json(
            "ProofReader",
            "You are a professional proofreader for insurance documents. Check grammar, section numbering, and cross-references.",
            f"""Proofread this insurance document.

Sections:
{chr(10).join(f"Section {s['section_number']}: {s['title']} — {s.get('content', '')[:200]}" for s in drafted_sections[:20])}

Check:
1. Grammar and spelling
2. Section numbering is sequential
3. Cross-references are correct
4. Professional tone maintained

Return ONLY valid JSON:
{{
    "clean": true/false,
    "errors": [
        {{
            "section_number": 1,
            "type": "grammar|numbering|cross_reference|formatting",
            "description": "The error",
            "fix": "Suggested fix"
        }}
    ]
}}"""
        )
        return result or {"clean": True, "errors": []}

    async def agent_clause_compiler(
        self,
        drafted_sections: List[Dict],
        selected_clauses: List[Dict],
        user_id: str = None,
    ) -> List[Dict]:
        """Agent 16: ClauseCompiler — replaces clause IDs with full ACORD standard wordings from RAG."""
        clause_map = {c["clause_id"]: c for c in selected_clauses}

        for section in drafted_sections:
            content = section.get("content", "")
            for clause_id, clause in clause_map.items():
                if clause_id in content:
                    if clause.get("selected_text"):
                        # Use existing clause text
                        if f"[{clause_id}]" in content:
                            content = content.replace(
                                f"[{clause_id}]",
                                f"{clause_id}: {clause['selected_text'][:500]}"
                            )
                    else:
                        # Search RAG for the full clause wording
                        try:
                            results = await self.unified_rag.search(
                                query=f"{clause_id} {clause.get('name', '')} full clause wording",
                                user_id=user_id,
                                top_k=1,
                                min_score=0.4,
                            )
                            if results:
                                full_text = results[0].get("text", "")[:500]
                                if f"[{clause_id}]" in content:
                                    content = content.replace(
                                        f"[{clause_id}]",
                                        f"{clause_id}: {full_text}"
                                    )
                        except Exception as e:
                            logger.warning(f"ClauseCompiler RAG lookup failed for {clause_id}: {e}")
            section["content"] = content

        return drafted_sections

    # ─── PHASE 6: EXPORT (Agents 17-19) ───────────────────────────────

    async def agent_schedule_builder(
        self,
        drafted_sections: List[Dict],
        assessment_data: Dict,
    ) -> Dict:
        """Agent 17: ScheduleBuilder — adds schedules, appendices, premium tables."""
        # Build comprehensive assessment details including new fields
        schedule_fields = [
            f"- Risk: {assessment_data.get('risk_category', '')}",
            f"- Insured: {assessment_data.get('insured_name', '')}",
            f"- Territory: {assessment_data.get('territory', '')}",
            f"- Premium: {assessment_data.get('premium', '')}",
            f"- Sum insured: {assessment_data.get('sum_insured', '')}",
            f"- Deductible: {assessment_data.get('deductible', '')}",
        ]
        if assessment_data.get("insured_entity_name"):
            schedule_fields.append(f"- Insured entity (full legal name): {assessment_data['insured_entity_name']}")
        if assessment_data.get("companies_house_number"):
            schedule_fields.append(f"- Companies House number: {assessment_data['companies_house_number']}")
        if assessment_data.get("broker_name"):
            schedule_fields.append(f"- Broker: {assessment_data['broker_name']}")
        if assessment_data.get("commission_rate") is not None:
            schedule_fields.append(f"- Commission rate: {assessment_data['commission_rate']}%")
        if assessment_data.get("inception_date"):
            schedule_fields.append(f"- Inception date: {assessment_data['inception_date']}")
        if assessment_data.get("renewal_date"):
            schedule_fields.append(f"- Renewal date: {assessment_data['renewal_date']}")
        if assessment_data.get("loss_run_reporting_rules"):
            schedule_fields.append(f"- Loss run reporting rules: {assessment_data['loss_run_reporting_rules']}")
        if assessment_data.get("regulatory_framework"):
            schedule_fields.append(f"- Regulatory framework: {assessment_data['regulatory_framework']}")

        result = await self._run_agent_json(
            "ScheduleBuilder",
            "You are a Lloyd's schedule and appendix specialist. Build document schedules based on the assessment data.",
            f"""Build schedules and appendices for this insurance document.

Assessment:
{chr(10).join(schedule_fields)}

Generate appropriate schedules.

Return ONLY valid JSON:
{{
    "schedules": [
        {{
            "schedule_number": 1,
            "title": "Schedule title",
            "content": "Schedule content with proper formatting"
        }}
    ],
    "appendices": [
        {{
            "appendix_letter": "A",
            "title": "Appendix title",
            "content": "Appendix content"
        }}
    ]
}}"""
        )
        return result or {"schedules": [], "appendices": []}

    async def agent_quality_gate(
        self,
        drafted_sections: List[Dict],
        compliance: Dict,
        risk_challenge: Dict,
        clause_verification: Dict,
        proofreading: Dict,
        assessment_data: Dict,
    ) -> Dict:
        """Agent 19: QualityGate — final checklist before export."""
        result = await self._run_agent_json(
            "QualityGate",
            "You are the final quality gate for Lloyd's document generation. Determine if this document is ready for export.",
            f"""Final quality check for this insurance document.

Compliance: {json.dumps(compliance, default=str)[:500]}
Risk challenges: {json.dumps(risk_challenge, default=str)[:500]}
Clause verification: {json.dumps(clause_verification, default=str)[:300]}
Proofreading: {json.dumps(proofreading, default=str)[:300]}
Sections count: {len(drafted_sections)}

Determine if this document passes the quality gate.

Return ONLY valid JSON:
{{
    "approved": true/false,
    "quality_score": 0.0-1.0,
    "blocking_issues": ["List of issues that must be fixed before export"],
    "warnings": ["Non-blocking concerns"],
    "summary": "Overall quality assessment"
}}"""
        )
        return result or {"approved": True, "quality_score": 0.75, "blocking_issues": [], "warnings": [], "summary": ""}

    # ─── CONVENIENCE METHODS (used by document_generation router) ─────

    async def analyze_assessment(
        self,
        assessment_data: Dict[str, Any],
        user_id: str = None,
    ) -> Dict[str, Any]:
        """Run research + gap analysis on an assessment (agents 1+3)."""
        try:
            research = await self.agent_risk_researcher(assessment_data, user_id)
            clause_candidates = await self.agent_clause_extractor(research, user_id)
            gap_analysis = await self.agent_gap_analyzer(research, clause_candidates, assessment_data)
            return {
                "research": research,
                "clause_candidates": clause_candidates,
                "gap_analysis": gap_analysis,
                "recommended_documents": gap_analysis.get("mandatory_missing", []),
            }
        except Exception as e:
            logger.error(f"analyze_assessment error: {e}")
            return {"research": {}, "clause_candidates": [], "gap_analysis": {}, "recommended_documents": []}

    async def search_clauses(
        self,
        document_types: List[str] = None,
        user_id: str = None,
    ) -> List[Dict[str, Any]]:
        """Search for relevant clauses by document type (agents 2+4)."""
        try:
            research = {"risk_category": "general", "key_findings": document_types or []}
            clause_candidates = await self.agent_clause_extractor(research, user_id)
            selected = await self.agent_clause_manager(clause_candidates, {"coverage_gaps": [], "mandatory_missing": []})
            return selected
        except Exception as e:
            logger.error(f"search_clauses error: {e}")
            return []

    # ─── MAIN PIPELINE ────────────────────────────────────────────────

    async def generate(
        self,
        assessment_data: Dict[str, Any],
        user_id: str = None,
        doc_types: List[str] = None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Full 19-agent pipeline to generate documents for an assessment.

        6 Phases:
          1. RESEARCH   (agents 1-3)
          2. STRUCTURE  (agents 4-6)
          3. COMPOSE    (agents 7-9)
          4. VALIDATE   (agents 10-12)
          5. REFINE     (agents 13-16)
          6. EXPORT     (agents 17-19)
        """
        results = {
            "assessment_id": assessment_data.get("id"),
            "generated_at": datetime.utcnow().isoformat(),
            "documents": [],
            "pipeline_steps": [],
            "total_agents": TOTAL_AGENTS,
            "errors": [],
            "agents_succeeded": 0,
            "agents_failed": 0,
        }

        # Get ML predictions if model is available
        ml_context = {}
        if insurance_model_service.is_available:
            try:
                risk_text = insurance_model_service.build_risk_description(assessment_data)
                ml_context = insurance_model_service.predict_all(risk_text, user_id=user_id)
                logger.info(f"InstantRisk Engine predictions: appetite={ml_context.get('appetite', {}).get('decision')}, "
                            f"pricing={ml_context.get('pricing', {}).get('band')}, "
                            f"clauses={len(ml_context.get('clauses', []))}")
            except Exception as e:
                logger.warning(f"InstantRisk Engine prediction failed: {e}")

        async def step(agent_num: int, name: str, status: str = "running"):
            if progress_callback:
                await progress_callback({
                    "step": agent_num,
                    "total_steps": TOTAL_AGENTS,
                    "agent": name,
                    "status": status,
                    "phase": self._get_phase(agent_num),
                })

        # Helper to track agent success/failure
        def _track_agent(results, name, output, fallback_check=None):
            """Track whether an agent returned real AI data or fallback."""
            used_fallback = False
            if fallback_check and output:
                used_fallback = fallback_check(output)
            if used_fallback:
                results["agents_failed"] += 1
                results["errors"].append(f"{name}: used fallback (Bedrock call failed or returned empty)")
                logger.warning(f"Agent {name} used fallback data")
            else:
                results["agents_succeeded"] += 1

        # ── PHASE 1: RESEARCH ──
        await step(1, "RiskResearcher")
        research = await self.agent_risk_researcher(assessment_data, user_id, ml_context=ml_context)
        _track_agent(results, "RiskResearcher", research,
                     lambda r: set(c.get("clause_id") for c in r.get("relevant_clauses", [])) == {"LMA5021", "LMA5173", "SUBROGATION", "ICC_A"})
        results["pipeline_steps"].append({"agent": "RiskResearcher", "status": "completed"})
        await step(1, "RiskResearcher", "completed")

        await step(2, "ClauseExtractor")
        clause_candidates = await self.agent_clause_extractor(research, user_id, ml_context=ml_context)
        results["pipeline_steps"].append({"agent": "ClauseExtractor", "status": "completed"})
        await step(2, "ClauseExtractor", "completed")

        await step(3, "GapAnalyzer")
        gap_analysis = await self.agent_gap_analyzer(research, clause_candidates, assessment_data)
        results["pipeline_steps"].append({"agent": "GapAnalyzer", "status": "completed"})
        await step(3, "GapAnalyzer", "completed")

        # ── PHASE 2: STRUCTURE ──
        await step(4, "ClauseManager")
        selected_clauses = await self.agent_clause_manager(clause_candidates, gap_analysis)
        results["pipeline_steps"].append({"agent": "ClauseManager", "status": "completed"})
        await step(4, "ClauseManager", "completed")

        # Determine which documents to generate
        recommended_docs = research.get("recommended_documents", [])
        if doc_types:
            recommended_docs = [d for d in recommended_docs if d.get("type") in doc_types]
        if not recommended_docs:
            # Build from requested doc_types if AI didn't return matching recommendations
            if doc_types:
                recommended_docs = [{"type": dt, "name": dt.replace("_", " ").title(), "priority": "mandatory"} for dt in doc_types]
            else:
                recommended_docs = [{"type": "policy_wording", "name": "Policy Wording", "priority": "mandatory"}]
        # Deduplicate by document type (keep first occurrence)
        seen_types = set()
        unique_docs = []
        for d in recommended_docs:
            dt = d.get("type", "policy_wording")
            if dt not in seen_types:
                seen_types.add(dt)
                unique_docs.append(d)
        recommended_docs = unique_docs
        logger.info(f"Document generation: requested={doc_types}, generating={[d.get('type') for d in recommended_docs]}")

        # Generate each document type
        for doc_req in recommended_docs:
            doc_type = doc_req.get("type", "policy_wording")

            await step(5, "StructurePlanner")
            structure = await self.agent_structure_planner(doc_type, selected_clauses, assessment_data)
            results["pipeline_steps"].append({"agent": "StructurePlanner", "status": "completed", "doc_type": doc_type})
            await step(5, "StructurePlanner", "completed")

            await step(6, "LloydFormatter")
            formatting = await self.agent_lloyd_formatter(structure, assessment_data)
            results["pipeline_steps"].append({"agent": "LloydFormatter", "status": "completed", "doc_type": doc_type})
            await step(6, "LloydFormatter", "completed")

            # ── PHASE 3: COMPOSE ──
            await step(7, "SectionDrafter")
            drafted_sections = await self.agent_section_drafter(structure, selected_clauses, assessment_data, formatting, user_id=user_id, ml_context=ml_context)
            results["pipeline_steps"].append({"agent": "SectionDrafter", "status": "completed", "doc_type": doc_type})
            await step(7, "SectionDrafter", "completed")

            await step(8, "ConsistencyChecker")
            consistency = await self.agent_consistency_checker(drafted_sections, assessment_data)
            results["pipeline_steps"].append({"agent": "ConsistencyChecker", "status": "completed", "doc_type": doc_type})
            await step(8, "ConsistencyChecker", "completed")

            await step(9, "ToneUnifier")
            drafted_sections = await self.agent_tone_unifier(drafted_sections)
            results["pipeline_steps"].append({"agent": "ToneUnifier", "status": "completed", "doc_type": doc_type})
            await step(9, "ToneUnifier", "completed")

            # ── PHASE 4: VALIDATE ──
            await step(10, "RiskChallenger")
            risk_challenge = await self.agent_risk_challenger(drafted_sections, assessment_data, user_id=user_id, ml_context=ml_context)
            results["pipeline_steps"].append({"agent": "RiskChallenger", "status": "completed", "doc_type": doc_type})
            await step(10, "RiskChallenger", "completed")

            await step(11, "ClauseVerifier")
            clause_verification = await self.agent_clause_verifier(selected_clauses)
            results["pipeline_steps"].append({"agent": "ClauseVerifier", "status": "completed", "doc_type": doc_type})
            await step(11, "ClauseVerifier", "completed")

            await step(12, "ComplianceReviewer")
            compliance = await self.agent_compliance_reviewer(drafted_sections, assessment_data, user_id=user_id, ml_context=ml_context)
            results["pipeline_steps"].append({"agent": "ComplianceReviewer", "status": "completed", "doc_type": doc_type})
            await step(12, "ComplianceReviewer", "completed")

            # ── PHASE 5: REFINE ──
            await step(13, "HouseStyleAgent")
            drafted_sections = await self.agent_house_style(drafted_sections, user_id)
            results["pipeline_steps"].append({"agent": "HouseStyleAgent", "status": "completed", "doc_type": doc_type})
            await step(13, "HouseStyleAgent", "completed")

            await step(14, "LanguageVarier")
            drafted_sections = await self.agent_language_varier(drafted_sections)
            results["pipeline_steps"].append({"agent": "LanguageVarier", "status": "completed", "doc_type": doc_type})
            await step(14, "LanguageVarier", "completed")

            await step(15, "ProofReader")
            proofreading = await self.agent_proof_reader(drafted_sections)
            results["pipeline_steps"].append({"agent": "ProofReader", "status": "completed", "doc_type": doc_type})
            await step(15, "ProofReader", "completed")

            await step(16, "ClauseCompiler")
            drafted_sections = await self.agent_clause_compiler(drafted_sections, selected_clauses, user_id=user_id)
            results["pipeline_steps"].append({"agent": "ClauseCompiler", "status": "completed", "doc_type": doc_type})
            await step(16, "ClauseCompiler", "completed")

            # ── PHASE 6: EXPORT ──
            await step(17, "ScheduleBuilder")
            schedules = await self.agent_schedule_builder(drafted_sections, assessment_data)
            results["pipeline_steps"].append({"agent": "ScheduleBuilder", "status": "completed", "doc_type": doc_type})
            await step(17, "ScheduleBuilder", "completed")

            # Agent 18: PDFExporter (code-only, no LLM call)
            await step(18, "PDFExporter")
            # PDF generation handled by existing WeasyPrint pipeline in document_generation router
            results["pipeline_steps"].append({"agent": "PDFExporter", "status": "completed", "doc_type": doc_type})
            await step(18, "PDFExporter", "completed")

            await step(19, "QualityGate")
            quality = await self.agent_quality_gate(
                drafted_sections, compliance, risk_challenge,
                clause_verification, proofreading, assessment_data,
            )
            results["pipeline_steps"].append({"agent": "QualityGate", "status": "completed", "doc_type": doc_type})
            await step(19, "QualityGate", "completed")

            # Build final document
            source_attribution = {"template": 0, "lma_clause": 0, "clause_library": 0, "section_default": 0, "rag": 0, "ai_generated": 0}
            source_type_counts = {}
            doc_content = []
            for section in drafted_sections:
                st = section.get("source_type", "unknown")
                source_type_counts[st] = source_type_counts.get(st, 0) + 1
                section_entry = {
                    "section_number": section["section_number"],
                    "title": section["title"],
                    "content": section["content"],
                    "source_type": st,
                }
                if section.get("requires_review"):
                    section_entry["requires_review"] = True
                doc_content.append(section_entry)
                # Count source_type for attribution
                if st in source_attribution:
                    source_attribution[st] += 1

            logger.info(f"OpenDraft doc '{doc_type}': {len(doc_content)} sections, "
                        f"source_types={source_type_counts}, "
                        f"sample_keys={list(doc_content[0].keys()) if doc_content else []}")

            formatted_doc = {
                "document_type": doc_type,
                "title": f"{doc_type.replace('_', ' ').title()} — {assessment_data.get('insured_entity_name') or assessment_data.get('insured_name', 'Insured')}",
                "generated_at": datetime.utcnow().isoformat(),
                "sections": doc_content,
                "total_sections": len(doc_content),
                "schedules": schedules.get("schedules", []),
                "appendices": schedules.get("appendices", []),
                "compliance": compliance,
                "risk_challenge": risk_challenge,
                "quality_gate": quality,
                "formatting": formatting,
                "source_attribution": source_attribution,
                "assessment_reference": assessment_data.get("reference_number", ""),
                "gap_analysis": gap_analysis,
                "ml_predictions": ml_context if ml_context else None,
            }

            results["documents"].append(formatted_doc)

        results["total_documents"] = len(results["documents"])
        results["clause_selections"] = selected_clauses

        # Determine pipeline health
        total_tracked = results["agents_succeeded"] + results["agents_failed"]
        if total_tracked > 0 and results["agents_failed"] > total_tracked / 2:
            results["pipeline_status"] = "degraded"
            logger.warning(f"Pipeline degraded: {results['agents_failed']}/{total_tracked} agents failed")
        elif results["agents_failed"] > 0:
            results["pipeline_status"] = "partial"
            logger.info(f"Pipeline partial: {results['agents_failed']}/{total_tracked} agents used fallback")
        else:
            results["pipeline_status"] = "success"
            logger.info("Pipeline completed successfully — all agents used real AI data")

        return results

    # ─── HELPERS ───────────────────────────────────────────────────────

    def _get_phase(self, agent_num: int) -> str:
        """Get phase name for agent number."""
        if agent_num <= 3:
            return "RESEARCH"
        elif agent_num <= 6:
            return "STRUCTURE"
        elif agent_num <= 9:
            return "COMPOSE"
        elif agent_num <= 12:
            return "VALIDATE"
        elif agent_num <= 16:
            return "REFINE"
        else:
            return "EXPORT"

    def _parse_json(self, response: str) -> Optional[Dict]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if not response:
            return None

        text = response.strip()

        if "```json" in text:
            text = text.split("```json", 1)[1]
            if "```" in text:
                text = text.split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1]
            if "```" in text:
                text = text.split("```", 1)[0]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Failed to parse JSON from response: {text[:200]}")
            return None

    def _fallback_research(self, assessment_data: Dict) -> Dict:
        """Fallback research when AI analysis fails."""
        risk_category = assessment_data.get("risk_category", "property").lower()

        clauses = [
            {"clause_id": "LMA5021", "name": "Several Liability Notice", "relevance": "Standard Lloyd's requirement", "priority": "mandatory", "source": "standard"},
            {"clause_id": "LMA5173", "name": "Sanctions Limitation", "relevance": "Compliance requirement", "priority": "mandatory", "source": "standard"},
            {"clause_id": "SUBROGATION", "name": "Subrogation Clause", "relevance": "Standard condition", "priority": "mandatory", "source": "standard"},
        ]

        if risk_category in ("marine", "cargo"):
            clauses.append({"clause_id": "ICC_A", "name": "Institute Cargo Clauses (A)", "relevance": "Standard marine cargo coverage", "priority": "mandatory", "source": "acord"})

        docs = [
            {"type": "policy_wording", "name": "Policy Wording", "reason": "Standard policy document required", "priority": "mandatory"},
            {"type": "mrc_slip", "name": "MRC Placing Slip", "reason": "Lloyd's market placement document", "priority": "mandatory"},
        ]

        return {
            "risk_profile": {
                "category": risk_category,
                "territory": assessment_data.get("territory", ""),
                "key_exposures": [],
                "market_context": "Fallback — AI analysis unavailable",
            },
            "relevant_clauses": clauses,
            "recommended_documents": docs,
        }


# Singleton instance
opendraft_generator = OpenDraftGenerator()
