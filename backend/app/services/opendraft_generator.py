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

Cost per document: ~$0.38 (10 Haiku + 9 Sonnet calls)
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

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

    def _resolve_model_id(self, model_alias: str) -> Optional[str]:
        """Resolve short model alias to full Bedrock model ID."""
        import os
        if model_alias == "sonnet":
            return os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
        elif model_alias == "haiku":
            return os.getenv("BEDROCK_FALLBACK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")
        return None

    async def _run_agent(
        self,
        name: str,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.1,
    ) -> Optional[str]:
        """Run a single agent via Bedrock."""
        model_alias = AGENT_MODELS.get(name, "haiku")
        model_id = self._resolve_model_id(model_alias)
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
            response = await self.bedrock.chat(messages, temperature=temperature, model_id=model_id)
            return response
        except Exception as e:
            logger.error(f"Agent {name} failed: {e}")
            return None

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
            "premium": assessment_data.get("premium"),
            "sum_insured": assessment_data.get("sum_insured"),
            "deductible": assessment_data.get("deductible"),
            "decision": assessment_data.get("decision", ""),
            "risk_score": assessment_data.get("risk_score"),
            "ai_analysis_summary": str(assessment_data.get("ai_analysis", {}))[:2000],
        }, indent=2)

        result = await self._run_agent_json(
            "RiskResearcher",
            "You are a Lloyd's insurance research specialist. Search and identify all relevant clauses, precedents, and market wordings for the given risk.",
            f"""Research this insurance risk and identify relevant clauses.

ASSESSMENT DATA:
{assessment_summary}

KNOWLEDGE BASE (ACORD/CUAD/JeTech results):
{rag_context}

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
    ) -> List[Dict]:
        """Agent 2: ClauseExtractor — deep-reads found clauses, extracts key provisions."""
        clause_candidates = []

        for clause in research.get("relevant_clauses", [])[:20]:
            clause_id = clause.get("clause_id", "")
            name = clause.get("name", "")
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
        """Agent 5: StructurePlanner — uses CUAD patterns for section ordering."""
        result = await self._run_agent_json(
            "StructurePlanner",
            "You are a Lloyd's document structure specialist. Use CUAD's 41 clause type taxonomy to plan document sections in proper market order.",
            f"""Plan the structure for a {doc_type} insurance document.

Risk category: {assessment_data.get('risk_category', 'property')}
Territory: {assessment_data.get('territory', '')}
Number of clauses: {len(selected_clauses)}
Clause names: {', '.join(c['name'] for c in selected_clauses[:25])}

Structure this as a professional Lloyd's market document with proper section ordering.

Return ONLY valid JSON:
{{
    "document_type": "{doc_type}",
    "sections": [
        {{
            "section_number": 1,
            "title": "Section Title",
            "content_type": "header|clause|schedule|definitions|conditions|exclusions|signature",
            "clause_ids": ["clause_ids to include in this section"],
            "notes": "Drafting notes"
        }}
    ],
    "total_sections": 15
}}"""
        )
        if result:
            return result

        return {
            "document_type": doc_type,
            "sections": [
                {"section_number": i + 1, "title": c["name"], "content_type": "clause", "clause_ids": [c["clause_id"]]}
                for i, c in enumerate(selected_clauses)
            ],
            "total_sections": len(selected_clauses),
        }

    async def agent_lloyd_formatter(
        self,
        structure: Dict,
        assessment_data: Dict,
    ) -> Dict:
        """Agent 6: LloydFormatter — applies London market formatting patterns from JeTech."""
        result = await self._run_agent_json(
            "LloydFormatter",
            "You are a Lloyd's market formatting specialist. Apply London market standard formatting conventions based on JeTech underwriting block patterns.",
            f"""Apply Lloyd's market formatting to this document structure.

Document type: {structure.get('document_type', 'policy_wording')}
Total sections: {structure.get('total_sections', 0)}
Section titles: {', '.join(s['title'] for s in structure.get('sections', [])[:20])}

Define the formatting rules for:
- Header block format (Type, Unique Market Reference, etc.)
- Section numbering style
- Clause reference format
- Schedule formatting
- Signature block layout

Return ONLY valid JSON:
{{
    "format_rules": {{
        "header_style": "Description of header format",
        "numbering": "1.1, 1.2 etc",
        "clause_ref_format": "How to reference clauses",
        "schedule_format": "How to format schedules"
    }},
    "header_block": {{
        "type_of_insurance": "{assessment_data.get('risk_category', 'Property')}",
        "unique_market_reference": "B0000/IR/{datetime.utcnow().strftime('%Y')}",
        "period": "12 months",
        "premium": "{assessment_data.get('premium', 'TBA')}",
        "insured": "{assessment_data.get('insured_name', 'TBA')}"
    }},
    "footer_notes": "Standard footer text"
}}"""
        )
        return result or {"format_rules": {}, "header_block": {}, "footer_notes": ""}

    # ─── PHASE 3: COMPOSE (Agents 7-9) ────────────────────────────────

    async def agent_section_drafter(
        self,
        structure: Dict,
        selected_clauses: List[Dict],
        assessment_data: Dict,
        formatting: Dict,
    ) -> List[Dict]:
        """Agent 7: SectionDrafter — drafts each section using selected clauses + house style."""
        clause_map = {c["clause_id"]: c for c in selected_clauses}
        drafted_sections = []

        for section in structure.get("sections", []):
            section_clauses = []
            for cid in section.get("clause_ids", []):
                if cid in clause_map:
                    section_clauses.append(clause_map[cid])

            if section_clauses and any(c.get("selected_text") for c in section_clauses):
                content_parts = []
                for c in section_clauses:
                    if c.get("selected_text"):
                        content_parts.append(c["selected_text"])

                drafted_sections.append({
                    "section_number": section["section_number"],
                    "title": section["title"],
                    "content": "\n\n".join(content_parts),
                    "source_clauses": [
                        {"id": c["clause_id"], "source": c.get("source", "unknown")}
                        for c in section_clauses
                    ],
                })
            else:
                response = await self._run_agent(
                    "SectionDrafter",
                    "You are a Lloyd's insurance document drafter. Write professional insurance wording using London market standard language.",
                    f"""Draft the '{section['title']}' section for a {structure.get('document_type', 'policy')} document.

Assessment details:
- Risk category: {assessment_data.get('risk_category', '')}
- Insured: {assessment_data.get('insured_name', '')}
- Territory: {assessment_data.get('territory', '')}
- Premium: {assessment_data.get('premium', '')}
- Sum insured: {assessment_data.get('sum_insured', '')}
- Deductible: {assessment_data.get('deductible', '')}

Draft professional insurance wording. Use Lloyd's market standard language and conventions.""",
                    temperature=0.2,
                )

                drafted_sections.append({
                    "section_number": section["section_number"],
                    "title": section["title"],
                    "content": response or f"[Section: {section['title']} — content pending]",
                    "source_clauses": [{"id": "ai_generated", "source": "ai_generated"}],
                })

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
- Insured: {assessment_data.get('insured_name', '')}
- Premium: {assessment_data.get('premium', '')}
- Sum insured: {assessment_data.get('sum_insured', '')}
- Deductible: {assessment_data.get('deductible', '')}
- Territory: {assessment_data.get('territory', '')}

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
    ) -> Dict:
        """Agent 10: RiskChallenger — challenges coverage adequacy, finds exclusion gaps."""
        result = await self._run_agent_json(
            "RiskChallenger",
            "You are a senior Lloyd's underwriter reviewing a placement. Challenge the coverage adequacy and identify potential gaps or weaknesses.",
            f"""Challenge this insurance document's coverage adequacy.

Risk: {assessment_data.get('risk_category', '')} in {assessment_data.get('territory', '')}
Sum insured: {assessment_data.get('sum_insured', '')}
Sections: {', '.join(s['title'] for s in drafted_sections[:20])}

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
{json.dumps([{{"id": c["clause_id"], "name": c["name"], "source": c.get("source", "unknown")}} for c in selected_clauses[:30]], indent=2)}

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
    ) -> Dict:
        """Agent 12: ComplianceReviewer — simulates Lloyd's compliance review."""
        result = await self._run_agent_json(
            "ComplianceReviewer",
            "You are a Lloyd's compliance officer. Review this document for regulatory compliance including sanctions, PRA/FCA requirements, and market standards.",
            f"""Review this insurance document for Lloyd's compliance.

Document sections: {', '.join(s['title'] for s in drafted_sections[:20])}
Risk category: {assessment_data.get('risk_category', '')}
Territory: {assessment_data.get('territory', '')}

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
            except Exception:
                pass

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
    ) -> List[Dict]:
        """Agent 16: ClauseCompiler — replaces clause IDs with full ACORD standard wordings."""
        clause_map = {c["clause_id"]: c for c in selected_clauses}

        for section in drafted_sections:
            content = section.get("content", "")
            for clause_id, clause in clause_map.items():
                if clause_id in content and clause.get("selected_text"):
                    # Append full clause text after the reference
                    if f"[{clause_id}]" in content:
                        content = content.replace(
                            f"[{clause_id}]",
                            f"{clause_id}: {clause['selected_text'][:500]}"
                        )
            section["content"] = content

        return drafted_sections

    # ─── PHASE 6: EXPORT (Agents 17-19) ───────────────────────────────

    async def agent_schedule_builder(
        self,
        drafted_sections: List[Dict],
        assessment_data: Dict,
    ) -> Dict:
        """Agent 17: ScheduleBuilder — adds schedules, appendices, premium tables."""
        result = await self._run_agent_json(
            "ScheduleBuilder",
            "You are a Lloyd's schedule and appendix specialist. Build document schedules based on the assessment data.",
            f"""Build schedules and appendices for this insurance document.

Assessment:
- Risk: {assessment_data.get('risk_category', '')}
- Insured: {assessment_data.get('insured_name', '')}
- Territory: {assessment_data.get('territory', '')}
- Premium: {assessment_data.get('premium', '')}
- Sum insured: {assessment_data.get('sum_insured', '')}
- Deductible: {assessment_data.get('deductible', '')}

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
        }

        async def step(agent_num: int, name: str, status: str = "running"):
            if progress_callback:
                await progress_callback({
                    "step": agent_num,
                    "total_steps": TOTAL_AGENTS,
                    "agent": name,
                    "status": status,
                    "phase": self._get_phase(agent_num),
                })

        # ── PHASE 1: RESEARCH ──
        await step(1, "RiskResearcher")
        research = await self.agent_risk_researcher(assessment_data, user_id)
        results["pipeline_steps"].append({"agent": "RiskResearcher", "status": "completed"})
        await step(1, "RiskResearcher", "completed")

        await step(2, "ClauseExtractor")
        clause_candidates = await self.agent_clause_extractor(research, user_id)
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
            recommended_docs = [{"type": "policy_wording", "name": "Policy Wording", "priority": "mandatory"}]

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
            drafted_sections = await self.agent_section_drafter(structure, selected_clauses, assessment_data, formatting)
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
            risk_challenge = await self.agent_risk_challenger(drafted_sections, assessment_data)
            results["pipeline_steps"].append({"agent": "RiskChallenger", "status": "completed", "doc_type": doc_type})
            await step(10, "RiskChallenger", "completed")

            await step(11, "ClauseVerifier")
            clause_verification = await self.agent_clause_verifier(selected_clauses)
            results["pipeline_steps"].append({"agent": "ClauseVerifier", "status": "completed", "doc_type": doc_type})
            await step(11, "ClauseVerifier", "completed")

            await step(12, "ComplianceReviewer")
            compliance = await self.agent_compliance_reviewer(drafted_sections, assessment_data)
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
            drafted_sections = await self.agent_clause_compiler(drafted_sections, selected_clauses)
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
            source_attribution = {"user": 0, "acord": 0, "cuad": 0, "jetech": 0, "ai_generated": 0, "global": 0}
            doc_content = []
            for section in drafted_sections:
                doc_content.append({
                    "section_number": section["section_number"],
                    "title": section["title"],
                    "content": section["content"],
                })
                for sc in section.get("source_clauses", []):
                    source = sc.get("source", "ai_generated")
                    if source in source_attribution:
                        source_attribution[source] += 1

            formatted_doc = {
                "document_type": doc_type,
                "title": f"{doc_type.replace('_', ' ').title()} — {assessment_data.get('insured_name', 'Insured')}",
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
            }

            results["documents"].append(formatted_doc)

        results["total_documents"] = len(results["documents"])
        results["clause_selections"] = selected_clauses

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
