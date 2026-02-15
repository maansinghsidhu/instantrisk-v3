"""
AutoGen-based Document Generation Pipeline
5-Agent System for AI-Powered Insurance Document Generation

Agents:
1. DocumentRequirementAnalyzer - Determines required documents from assessment
2. TemplateSelector - Matches requirements to best templates
3. DataMapper - Maps assessment data to template fields
4. DocumentDrafter - Generates document content with AI
5. ComplianceChecker - Validates generated documents

FIXES IMPLEMENTED:
- Retry logic with exponential backoff for JSON parsing failures
- Comprehensive error tracking and user-visible error messages
- Improved prompts with strict JSON formatting requirements
- Pre-population of fields from assessment data before AI processing
"""

import os
import json
import uuid
import logging
import asyncio
import re
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from decimal import Decimal

from app.services.autogen_processor import AgentProgress
from app.services.bedrock_client import BedrockClient as _BedrockClientClass

logger = logging.getLogger(__name__)

# Maximum retries for AI calls
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


# =============================================================================
# DOCUMENT REQUIREMENTS MAPPING
# =============================================================================
DOCUMENT_REQUIREMENTS = {
    "property": {
        "primary": ["property_policy"],
        "required": ["certificate_of_insurance"],
        "conditional": {
            "multiple_locations": ["schedule_of_locations"],
            "high_value": ["loss_payee_endorsement"],
        }
    },
    "cyber": {
        "primary": ["cyber_liability"],
        "required": ["certificate_of_insurance"],
        "optional": ["data_breach_response_plan"],
        "conditional": {
            "pci_compliance": ["pci_compliance_addendum"],
        }
    },
    "marine": {
        "primary": ["marine_cargo"],
        "required": ["certificate_of_insurance"],
        "optional": ["bill_of_lading_template"],
        "conditional": {
            "war_risks": ["war_risks_endorsement"],
        }
    },
    "professional": {
        "primary": ["professional_indemnity"],
        "required": ["certificate_of_insurance"],
        "conditional": {
            "extended_reporting": ["erp_endorsement"],
        }
    },
    "casualty": {
        "primary": ["general_liability_policy"],
        "required": ["certificate_of_insurance"],
        "conditional": {
            "additional_insured": ["additional_insured_endorsement"],
        }
    },
    "aviation": {
        "primary": ["aviation_policy"],
        "required": ["certificate_of_insurance"],
    },
    "energy": {
        "primary": ["energy_policy"],
        "required": ["certificate_of_insurance"],
    },
    "financial_lines": {
        "primary": ["financial_lines_policy"],
        "required": ["certificate_of_insurance"],
    },
    "specialty": {
        "primary": ["specialty_policy"],
        "required": ["certificate_of_insurance"],
    },
    # Lloyd's placing always needs MRC slip
    "lloyds": {
        "primary": ["lloyds_mrc_slip"],
        "required": ["certificate_of_insurance"],
    }
}


# =============================================================================
# LMA CLAUSES BY RISK CATEGORY - Pre-selected based on risk type
# =============================================================================
LMA_CLAUSES_BY_CATEGORY = {
    # Core clauses for ALL risk types
    "_core": [
        {"id": "LMA5096", "name": "Several Liability Clause", "mandatory": True, "category": "general"},
        {"id": "LMA5001", "name": "Premium Payment Clause", "mandatory": True, "category": "general"},
        {"id": "LMA5147", "name": "English Law and Jurisdiction Clause", "mandatory": False, "category": "general"},
        {"id": "LMA5121", "name": "Nuclear Incident Exclusion Clause", "mandatory": True, "category": "general"},
        {"id": "LMA5212", "name": "War Exclusion Clause", "mandatory": True, "category": "war_terrorism"},
    ],
    "marine": [
        {"id": "ICC-A", "name": "Institute Cargo Clauses (A)", "mandatory": True, "category": "marine"},
        {"id": "ICC-B", "name": "Institute Cargo Clauses (B)", "mandatory": False, "category": "marine"},
        {"id": "ICC-C", "name": "Institute Cargo Clauses (C)", "mandatory": False, "category": "marine"},
        {"id": "LMA5403", "name": "Institute War Clauses (Cargo)", "mandatory": False, "category": "marine"},
        {"id": "LMA5404", "name": "Institute Strikes Clauses (Cargo)", "mandatory": False, "category": "marine"},
        {"id": "CL385", "name": "Institute Cyber Attack Exclusion Clause", "mandatory": True, "category": "cyber"},
    ],
    "property": [
        {"id": "LMA3100", "name": "Property Damage Clause", "mandatory": True, "category": "property"},
        {"id": "LMA5014", "name": "Contingent Business Interruption", "mandatory": False, "category": "property"},
        {"id": "CL380", "name": "Institute Cyber Attack Exclusion", "mandatory": True, "category": "cyber"},
    ],
    "cyber": [
        {"id": "LMA5400", "name": "Cyber Liability Coverage Clause", "mandatory": True, "category": "cyber"},
        {"id": "LMA5401", "name": "Data Breach Response Clause", "mandatory": True, "category": "cyber"},
        {"id": "LMA5402", "name": "Business Interruption (Cyber)", "mandatory": False, "category": "cyber"},
    ],
    "professional": [
        {"id": "LMA3001", "name": "Professional Services Definition", "mandatory": True, "category": "professional_lines"},
        {"id": "LMA3002", "name": "Claims Made Coverage Clause", "mandatory": True, "category": "professional_lines"},
        {"id": "LMA3003", "name": "Extended Reporting Period", "mandatory": False, "category": "professional_lines"},
    ],
    "casualty": [
        {"id": "LMA2001", "name": "Products Liability Clause", "mandatory": False, "category": "casualty"},
        {"id": "LMA2002", "name": "Completed Operations Coverage", "mandatory": False, "category": "casualty"},
        {"id": "LMA2003", "name": "Employers Liability Clause", "mandatory": False, "category": "casualty"},
    ],
    "aviation": [
        {"id": "AVN1", "name": "War, Hijacking and Other Perils Exclusion", "mandatory": True, "category": "aviation"},
        {"id": "AVN48B", "name": "Aviation Liability Coverage", "mandatory": True, "category": "aviation"},
        {"id": "AVN52E", "name": "Noise and Pollution Exclusion", "mandatory": False, "category": "aviation"},
    ],
    "energy": [
        {"id": "LSW1001", "name": "London Standard Energy Form", "mandatory": True, "category": "energy"},
        {"id": "LSW1002", "name": "Control of Well Coverage", "mandatory": False, "category": "energy"},
        {"id": "LSW1003", "name": "Operators Extra Expense", "mandatory": False, "category": "energy"},
    ],
    # Sanctions clauses - always recommended
    "_sanctions": [
        {"id": "LMA3100", "name": "Sanctions Limitation and Exclusion Clause", "mandatory": True, "category": "sanctions"},
        {"id": "LMA3101", "name": "Joint Financial Sanctions Clause", "mandatory": False, "category": "sanctions"},
    ]
}


# =============================================================================
# LLOYD'S STANDARD SECTIONS FOR EACH DOCUMENT TYPE
# =============================================================================
LLOYDS_DOCUMENT_SECTIONS = {
    "lloyds_mrc_slip": [
        "risk_details", "the_assured", "period", "interest", "territorial_limits",
        "basis_of_cover", "limit_of_liability", "deductible", "premium",
        "conditions_precedent", "subjectivities", "warranties", "exclusions",
        "extensions", "claims_conditions", "general_conditions", "jurisdiction",
        "service_of_suit", "several_liability", "security"
    ],
    "lloyds_policy_wording": [
        "declarations", "insuring_agreements", "definitions", "exclusions",
        "conditions", "claims", "general_provisions", "endorsements"
    ],
    "lloyds_cover_note": [
        "header", "cover_note_reference", "status_declaration", "insured_details",
        "coverage_period", "coverage_details", "territory", "premium", "deductibles",
        "underwriter_notes", "conditions", "exclusions", "claims_notification",
        "lead_underwriter", "coverholder_details", "important_notices", "governing_law"
    ],
    "lloyds_quote": [
        "header", "reference", "insured", "coverage_summary", "premium_indication",
        "terms_and_conditions", "validity", "next_steps"
    ],
    "certificate_of_insurance": [
        "certificate_holder", "insured", "coverage_type", "policy_number",
        "effective_date", "expiration_date", "limits", "description_of_operations",
        "certificate_holder_notice", "authorized_signature"
    ]
}


# =============================================================================
# IMPROVED AGENT PROMPTS WITH STRICT JSON FORMATTING
# =============================================================================
REQUIREMENT_ANALYZER_PROMPT = """You are a Lloyd's documentation specialist.
Based on the risk assessment, determine which insurance documents must be generated.

DOCUMENT TYPES AVAILABLE:
- lloyds_mrc_slip: Lloyd's Market Reform Contract slip (for Lloyd's placements)
- lloyds_policy_wording: Full policy wording document
- lloyds_cover_note: Temporary cover note pending policy issuance
- lloyds_quote: Non-binding indication or firm quote
- certificate_of_insurance: Proof of coverage for third parties
- property_policy: Commercial property insurance policy
- cyber_liability: Cyber liability and data breach policy
- professional_indemnity: Professional indemnity / E&O policy
- marine_cargo: Marine cargo insurance policy
- endorsement: Policy endorsement/amendment
- schedule_of_locations: Multi-location schedule
- general_liability_policy: General/public liability policy

RULES:
1. Lloyd's market placements ALWAYS need lloyds_mrc_slip
2. All GO decisions need certificate_of_insurance
3. Primary policy document based on risk category
4. Endorsements for special conditions

CRITICAL: You MUST respond with ONLY a valid JSON object. No explanatory text before or after.
Do not include markdown code blocks. Start directly with { and end with }.

Required JSON structure:
{
    "required_documents": [
        {
            "document_type": "type_from_list_above",
            "template_key": "matching template key",
            "priority": 1,
            "mandatory": true,
            "confidence": 0.95,
            "reason": "Why this document is needed",
            "auto_generate": true
        }
    ],
    "bundle_name": "Name for this document set",
    "total_documents": 1,
    "special_considerations": ["Any special handling notes"]
}

CONFIDENCE SCORING:
- 0.95-1.0: Essential document for this risk type (e.g., MRC slip for Lloyd's)
- 0.85-0.94: Strongly recommended based on risk profile
- 0.70-0.84: Beneficial based on assessment details
- 0.50-0.69: Optional but potentially useful"""


TEMPLATE_SELECTOR_PROMPT = """You are an insurance template matching specialist.
Match required documents to the best available templates.

AVAILABLE TEMPLATES:
{templates}

For each required document, select the best matching template.

CRITICAL: You MUST respond with ONLY a valid JSON object. No explanatory text before or after.
Do not include markdown code blocks. Start directly with { and end with }.

Required JSON structure:
{
    "template_selections": [
        {
            "document_type": "from requirements",
            "template_id": "template_id_string",
            "template_key": "template_key",
            "template_name": "human readable name",
            "match_confidence": 0.95,
            "customization_needed": false,
            "missing_fields": []
        }
    ],
    "all_templates_matched": true,
    "unmatched_documents": []
}"""


DATA_MAPPER_PROMPT = """You are an insurance data mapping specialist.
Map assessment and document data to template fields.

ASSESSMENT DATA:
{assessment_data}

DOCUMENT DATA (from OCR):
{document_data}

TEMPLATE FIELDS TO POPULATE:
{template_fields}

For each field, find the best matching data and specify confidence.

CRITICAL: You MUST respond with ONLY a valid JSON object. No explanatory text before or after.
Do not include markdown code blocks. Start directly with { and end with }.

Required JSON structure:
{
    "field_mappings": {
        "field_name": {
            "value": "extracted or computed value",
            "source": "assessment",
            "confidence": 0.95,
            "transformation": "none",
            "requires_review": false
        }
    },
    "unmapped_fields": [],
    "data_conflicts": [],
    "completion_percentage": 85,
    "notes": "Mapping notes"
}"""


DOCUMENT_DRAFTER_PROMPT = """You are an expert Lloyd's insurance document drafter.
Generate professional insurance document content following Lloyd's market standards.

DOCUMENT TYPE: {document_type}

TEMPLATE SECTIONS TO GENERATE:
{template_sections}

MAPPED DATA (use these values):
{field_mappings}

ASSESSMENT CONTEXT:
{assessment_summary}

REQUIREMENTS:
1. Use Lloyd's market standard language and terminology
2. Create clear and unambiguous clauses
3. Use proper legal terminology
4. Generate ALL required sections with full content
5. For missing data, use clear placeholders like [INSURED_NAME], [AMOUNT_TBD]
6. Each section must have substantial content (minimum 50 words per section)

CRITICAL: You MUST respond with ONLY a valid JSON object. No explanatory text before or after.
Do not include markdown code blocks. Start directly with a single { and end with a single }.

Required JSON structure:
{{
    "document_title": "Full document title",
    "sections": [
        {{
            "section_name": "section_identifier",
            "section_title": "Display Title",
            "content": "Full generated content with Lloyd's standard language. Must be detailed and complete.",
            "is_complete": true,
            "placeholders": []
        }}
    ],
    "total_placeholders": 0,
    "ready_for_review": true,
    "draft_notes": "Notes for reviewer"
}}"""


COMPLIANCE_CHECKER_PROMPT = """You are a Lloyd's compliance specialist.
Validate the generated document for regulatory and market compliance.

DOCUMENT TO VALIDATE:
{draft_document}

COMPLIANCE CHECKS:
1. Lloyd's Market Reform Contract (MRC) standards
2. All mandatory fields populated
3. Required sections present with adequate content
4. Proper signatures/authorization placeholders
5. Premium/limits clearly stated
6. Policy period clearly defined
7. Territorial limits specified
8. Exclusions and conditions clearly stated

CRITICAL: You MUST respond with ONLY a valid JSON object. No explanatory text before or after.
Do not include markdown code blocks. Start directly with a single { and end with a single }.

Required JSON structure:
{{
    "compliance_passed": true,
    "compliance_score": 85,
    "critical_issues": [],
    "warnings": [],
    "completeness_check": {{
        "mandatory_fields_present": 10,
        "mandatory_fields_missing": 2,
        "required_sections_present": 8,
        "required_sections_missing": 0
    }},
    "regulatory_notes": [],
    "approved_for_generation": true,
    "manual_review_required": false,
    "review_reason": ""
}}"""


class DocumentGenerationProgress:
    """Track document generation progress across agents."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.steps: List[Dict] = []
        self.current_agent: str = ""
        self.current_description: str = ""
        self.start_time: datetime = None
        self.total_documents: int = 0
        self.completed_documents: int = 0
        self.failed_documents: int = 0
        self.progress_percentage: int = 0
        self.errors: List[Dict] = []

    def start_agent(self, agent_name: str, description: str):
        self.current_agent = agent_name
        self.current_description = description
        self.start_time = datetime.now(timezone.utc)
        self.steps.append({
            "agent": agent_name,
            "status": "running",
            "description": description,
            "started_at": self.start_time.isoformat(),
            "completed_at": None,
            "duration_ms": None,
            "output_preview": None,
            "retries": 0
        })

    def complete_agent(self, output_preview: str = None):
        if self.steps:
            end_time = datetime.now(timezone.utc)
            self.steps[-1]["status"] = "completed"
            self.steps[-1]["completed_at"] = end_time.isoformat()
            self.steps[-1]["duration_ms"] = int((end_time - self.start_time).total_seconds() * 1000)
            self.steps[-1]["output_preview"] = output_preview[:200] if output_preview else None

    def fail_agent(self, error: str):
        if self.steps:
            self.steps[-1]["status"] = "failed"
            self.steps[-1]["error"] = error
        self.errors.append({
            "agent": self.current_agent,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def record_retry(self):
        if self.steps:
            self.steps[-1]["retries"] = self.steps[-1].get("retries", 0) + 1

    def update_progress(self, percentage: int):
        self.progress_percentage = percentage

    def add_error(self, document_type: str, error: str):
        """Add document-specific error for user visibility."""
        self.errors.append({
            "document_type": document_type,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self.failed_documents += 1

    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "current_agent": self.current_agent,
            "current_description": self.current_description,
            "progress_percentage": self.progress_percentage,
            "total_documents": self.total_documents,
            "completed_documents": self.completed_documents,
            "failed_documents": self.failed_documents,
            "steps": self.steps,
            "errors": self.errors
        }


class DocumentGenerationPipeline:
    """
    5-Agent Document Generation System with Production-Quality Features.

    Pipeline:
    1. DocumentRequirementAnalyzer - Determine required documents
    2. TemplateSelector - Match to templates
    3. DataMapper - Map assessment data to fields
    4. DocumentDrafter - Generate content
    5. ComplianceChecker - Validate compliance

    Features:
    - Retry logic with exponential backoff
    - Comprehensive error tracking
    - Pre-populated field mappings from assessment
    - Improved prompts for consistent JSON output
    """

    def __init__(self):
        self.llm = _BedrockClientClass()

    async def _call_llm_with_retry(
        self,
        messages: List[Dict],
        temperature: float = 0.1,
        max_tokens: int = 4000,
        progress: DocumentGenerationProgress = None
    ) -> str:
        """Call LLM with retry logic for failures."""
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.llm.chat(messages, temperature=temperature, max_tokens=max_tokens)

                if response and response.strip():
                    return response

                logger.warning(f"Empty response from LLM, attempt {attempt + 1}/{MAX_RETRIES}")

            except Exception as e:
                last_error = e
                logger.error(f"LLM call failed, attempt {attempt + 1}/{MAX_RETRIES}: {e}")

            if progress:
                progress.record_retry()

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))

        raise Exception(f"LLM call failed after {MAX_RETRIES} attempts: {last_error}")

    def _parse_json_with_retry(self, content: str, context: str = "") -> Dict:
        """
        Parse JSON from agent response with multiple strategies.
        Returns empty dict with error info if all parsing fails.
        """
        if not content:
            logger.error(f"Empty content received for {context}")
            return {"_error": "Empty response from AI", "_context": context}

        original_content = content

        # Strategy 1: Direct parse
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code block
        try:
            content = original_content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
                return json.loads(content.strip())
            elif "```" in content:
                for part in content.split("```"):
                    part = part.strip()
                    if part.startswith("{") and part.endswith("}"):
                        return json.loads(part)
        except json.JSONDecodeError:
            pass

        # Strategy 3: Find JSON object in text
        try:
            content = original_content
            # Find first { and last }
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = content[start:end + 1]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Strategy 4: Try to fix common JSON issues
        try:
            content = original_content
            # Fix double braces (common AI mistake)
            content = content.replace('{{', '{').replace('}}', '}')
            # Remove trailing commas
            content = re.sub(r',\s*}', '}', content)
            content = re.sub(r',\s*]', ']', content)
            # Find JSON object
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                json_str = content[start:end + 1]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Strategy 5: Try to fix missing commas between properties/array items
        try:
            content = original_content
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                parts = content.split("```")
                for part in parts:
                    if "{" in part:
                        content = part
                        break

            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                json_str = content[start:end + 1]

                # Fix missing commas between string values and next property
                # Pattern: "value" followed by whitespace/newline then "key":
                json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
                # Pattern: } followed by whitespace/newline then {
                json_str = re.sub(r'}\s*\n\s*{', '},\n{', json_str)
                # Pattern: ] followed by whitespace/newline then "
                json_str = re.sub(r']\s*\n\s*"', '],\n"', json_str)
                # Pattern: true/false/null followed by whitespace/newline then "
                json_str = re.sub(r'(true|false|null)\s*\n\s*"', r'\1,\n"', json_str)
                # Pattern: number followed by whitespace/newline then "
                json_str = re.sub(r'(\d)\s*\n\s*"', r'\1,\n"', json_str)
                # Remove trailing commas (again after fixes)
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)

                return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for {context}: {e}")
            logger.error(f"Content preview: {original_content[:500]}...")

        # All strategies failed - return error dict
        return {
            "_error": f"Failed to parse JSON response",
            "_context": context,
            "_raw_preview": original_content[:500] if original_content else ""
        }

    def _pre_populate_field_mappings(self, assessment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pre-populate field mappings directly from assessment data.
        This ensures we have data even if AI mapping fails.
        """
        def safe_get(d, key, default=None):
            val = d.get(key)
            return val if val is not None else default

        def format_currency(amount, currency="GBP"):
            if amount is None:
                return None
            try:
                if isinstance(amount, (int, float, Decimal)):
                    return f"{currency} {amount:,.2f}"
            except (ValueError, TypeError, ArithmeticError):
                pass
            return str(amount)

        def format_date(date_val):
            if not date_val:
                return None
            if isinstance(date_val, str):
                return date_val
            if hasattr(date_val, 'strftime'):
                return date_val.strftime("%d %B %Y")
            return str(date_val)

        # Extract AI analysis data if available
        ai_analysis = safe_get(assessment, 'ai_analysis', {})
        agent_results = safe_get(ai_analysis, 'agent_results', {})
        extractor = safe_get(agent_results, 'extractor', {})
        classifier = safe_get(agent_results, 'classifier', {})

        # Extract nested data
        insured_data = safe_get(extractor, 'insured', {})
        broker_data = safe_get(extractor, 'broker', {})
        coverage_data = safe_get(extractor, 'coverage', {})
        financials = safe_get(extractor, 'financials', {})
        period = safe_get(extractor, 'period', {})
        policy_details = safe_get(extractor, 'policy_details', {})
        syndicate_info = safe_get(extractor, 'syndicate_info', {})

        mappings = {
            # Core Insured Information
            "insured_name": {
                "value": safe_get(assessment, 'insured_name') or safe_get(insured_data, 'name'),
                "source": "assessment",
                "confidence": 1.0 if assessment.get('insured_name') else 0.9,
                "requires_review": False
            },
            "insured_address": {
                "value": safe_get(insured_data, 'address'),
                "source": "extraction",
                "confidence": 0.9 if insured_data.get('address') else 0.0,
                "requires_review": not insured_data.get('address')
            },
            "insured_country": {
                "value": safe_get(insured_data, 'country'),
                "source": "extraction",
                "confidence": 0.9,
                "requires_review": False
            },
            "insured_business": {
                "value": safe_get(insured_data, 'industry'),
                "source": "extraction",
                "confidence": 0.85,
                "requires_review": False
            },
            "insured_entity_name": {
                "value": safe_get(assessment, 'insured_entity_name'),
                "source": "assessment",
                "confidence": 1.0 if assessment.get('insured_entity_name') else 0.0,
                "requires_review": not assessment.get('insured_entity_name')
            },
            "companies_house_number": {
                "value": safe_get(assessment, 'companies_house_number'),
                "source": "assessment",
                "confidence": 1.0 if assessment.get('companies_house_number') else 0.0,
                "requires_review": not assessment.get('companies_house_number')
            },

            # Financial Information
            "premium": {
                "value": format_currency(safe_get(assessment, 'premium') or safe_get(financials, 'premium')),
                "source": "assessment",
                "confidence": 1.0 if assessment.get('premium') else 0.9,
                "requires_review": False
            },
            "premium_numeric": {
                "value": safe_get(assessment, 'premium') or safe_get(financials, 'premium'),
                "source": "assessment",
                "confidence": 1.0,
                "requires_review": False
            },
            "sum_insured": {
                "value": format_currency(safe_get(assessment, 'sum_insured') or safe_get(financials, 'sum_insured')),
                "source": "assessment",
                "confidence": 1.0 if assessment.get('sum_insured') else 0.9,
                "requires_review": False
            },
            "sum_insured_numeric": {
                "value": safe_get(assessment, 'sum_insured') or safe_get(financials, 'sum_insured'),
                "source": "assessment",
                "confidence": 1.0,
                "requires_review": False
            },
            "deductible": {
                "value": format_currency(safe_get(assessment, 'deductible') or safe_get(financials, 'deductible')),
                "source": "assessment",
                "confidence": 0.9,
                "requires_review": not assessment.get('deductible')
            },
            "currency": {
                "value": safe_get(financials, 'currency', 'GBP'),
                "source": "extraction",
                "confidence": 0.95,
                "requires_review": False
            },

            # Policy Details
            "reference_number": {
                "value": safe_get(assessment, 'reference_number'),
                "source": "assessment",
                "confidence": 1.0,
                "requires_review": False
            },
            "unique_market_reference": {
                "value": safe_get(policy_details, 'unique_market_reference') or safe_get(assessment, 'reference_number'),
                "source": "extraction",
                "confidence": 0.95,
                "requires_review": False
            },
            "broker_reference": {
                "value": safe_get(assessment, 'broker_reference') or safe_get(broker_data, 'reference'),
                "source": "assessment",
                "confidence": 0.9,
                "requires_review": not assessment.get('broker_reference')
            },

            # Coverage Information
            "risk_category": {
                "value": safe_get(assessment, 'risk_category'),
                "source": "assessment",
                "confidence": 1.0,
                "requires_review": False
            },
            "coverage_type": {
                "value": safe_get(coverage_data, 'type') or safe_get(assessment, 'risk_category'),
                "source": "extraction",
                "confidence": 0.9,
                "requires_review": False
            },
            "territory": {
                "value": safe_get(assessment, 'territory') or safe_get(coverage_data, 'territorial_limits'),
                "source": "assessment",
                "confidence": 1.0 if assessment.get('territory') else 0.85,
                "requires_review": False
            },
            "perils_covered": {
                "value": safe_get(coverage_data, 'perils_covered', []),
                "source": "extraction",
                "confidence": 0.85,
                "requires_review": True
            },

            # Period
            "inception_date": {
                "value": format_date(safe_get(assessment, 'inception_date') or safe_get(period, 'inception_date')),
                "source": "assessment",
                "confidence": 0.9 if assessment.get('inception_date') or period.get('inception_date') else 0.0,
                "requires_review": not (assessment.get('inception_date') or period.get('inception_date'))
            },
            "expiry_date": {
                "value": format_date(safe_get(assessment, 'expiry_date') or safe_get(period, 'expiry_date')),
                "source": "assessment",
                "confidence": 0.9 if assessment.get('expiry_date') or period.get('expiry_date') else 0.0,
                "requires_review": not (assessment.get('expiry_date') or period.get('expiry_date'))
            },
            "period_months": {
                "value": safe_get(period, 'period_months', 12),
                "source": "extraction",
                "confidence": 0.9,
                "requires_review": False
            },
            "renewal_date": {
                "value": format_date(safe_get(assessment, 'renewal_date')),
                "source": "assessment",
                "confidence": 1.0 if assessment.get('renewal_date') else 0.0,
                "requires_review": not assessment.get('renewal_date')
            },

            # Regulatory
            "regulatory_framework": {
                "value": safe_get(assessment, 'regulatory_framework'),
                "source": "assessment",
                "confidence": 1.0 if assessment.get('regulatory_framework') else 0.0,
                "requires_review": not assessment.get('regulatory_framework')
            },
            "loss_run_reporting_rules": {
                "value": safe_get(assessment, 'loss_run_reporting_rules'),
                "source": "assessment",
                "confidence": 1.0 if assessment.get('loss_run_reporting_rules') else 0.0,
                "requires_review": not assessment.get('loss_run_reporting_rules')
            },

            # Broker Information
            "broker_name": {
                "value": safe_get(assessment, 'broker_name') or safe_get(broker_data, 'name'),
                "source": "assessment" if assessment.get('broker_name') else "extraction",
                "confidence": 1.0 if assessment.get('broker_name') else (0.9 if broker_data.get('name') else 0.0),
                "requires_review": not (assessment.get('broker_name') or broker_data.get('name'))
            },
            "commission_rate": {
                "value": f"{safe_get(assessment, 'commission_rate')}%" if assessment.get('commission_rate') else None,
                "source": "assessment",
                "confidence": 1.0 if assessment.get('commission_rate') else 0.0,
                "requires_review": not assessment.get('commission_rate')
            },
            "broker_contact": {
                "value": safe_get(broker_data, 'contact'),
                "source": "extraction",
                "confidence": 0.8,
                "requires_review": True
            },

            # Syndicate Information
            "lead_syndicate": {
                "value": None,
                "source": "manual_required",
                "confidence": 0.0,
                "requires_review": True
            },
            "signed_line": {
                "value": safe_get(syndicate_info, 'signed_line'),
                "source": "extraction",
                "confidence": 0.85,
                "requires_review": True
            },

            # Decision Information
            "decision": {
                "value": safe_get(assessment, 'decision'),
                "source": "assessment",
                "confidence": 1.0,
                "requires_review": False
            },
            "risk_score": {
                "value": safe_get(assessment, 'risk_score'),
                "source": "assessment",
                "confidence": 1.0,
                "requires_review": False
            },
            "decision_rationale": {
                "value": safe_get(assessment, 'decision_rationale'),
                "source": "assessment",
                "confidence": 1.0,
                "requires_review": False
            },

            # Document Classification
            "document_type": {
                "value": safe_get(classifier, 'document_type'),
                "source": "extraction",
                "confidence": safe_get(classifier, 'confidence', 0.9),
                "requires_review": False
            },
            "is_lloyds_market": {
                "value": safe_get(classifier, "lloyd's_market", True),
                "source": "extraction",
                "confidence": 0.95,
                "requires_review": False
            },

            # Generation metadata
            "generation_date": {
                "value": datetime.now(timezone.utc).strftime("%d %B %Y"),
                "source": "computed",
                "confidence": 1.0,
                "requires_review": False
            }
        }

        # Calculate completion percentage
        total_fields = len(mappings)
        populated = sum(1 for m in mappings.values() if m.get("value") is not None)
        completion = int((populated / total_fields) * 100) if total_fields > 0 else 0

        # Identify unmapped fields
        unmapped = [k for k, v in mappings.items() if v.get("value") is None]

        return {
            "field_mappings": mappings,
            "unmapped_fields": unmapped,
            "data_conflicts": [],
            "completion_percentage": completion,
            "notes": f"Pre-populated {populated}/{total_fields} fields from assessment data"
        }

    def _generate_fallback_document(
        self,
        document_type: str,
        field_mappings: Dict,
        assessment: Dict
    ) -> Dict:
        """
        Generate document content using templates when AI fails.
        This ensures we always have some content.
        """
        sections = LLOYDS_DOCUMENT_SECTIONS.get(document_type, [])
        fm = field_mappings.get("field_mappings", {})

        def get_val(key, default="[TO BE CONFIRMED]"):
            mapping = fm.get(key, {})
            val = mapping.get("value")
            return val if val is not None else default

        generated_sections = []
        placeholders = []

        # Generate content for each section based on document type
        if document_type == "lloyds_mrc_slip":
            generated_sections = self._generate_mrc_slip_sections(get_val, placeholders, assessment)
        elif document_type == "lloyds_policy_wording":
            generated_sections = self._generate_policy_wording_sections(get_val, placeholders, assessment)
        elif document_type == "lloyds_cover_note":
            generated_sections = self._generate_cover_note_sections(get_val, placeholders, assessment)
        elif document_type == "lloyds_quote":
            generated_sections = self._generate_quote_sections(get_val, placeholders, assessment)
        elif document_type == "property_policy":
            generated_sections = self._generate_property_policy_sections(get_val, placeholders, assessment)
        elif document_type == "certificate_of_insurance":
            generated_sections = self._generate_certificate_sections(get_val, placeholders, assessment)
        else:
            # Generic fallback
            for section in sections:
                generated_sections.append({
                    "section_name": section,
                    "section_title": section.replace("_", " ").title(),
                    "content": f"[Content for {section} section to be completed]",
                    "is_complete": False,
                    "placeholders": [f"{section.upper()}_CONTENT"]
                })
                placeholders.append(f"{section.upper()}_CONTENT")

        return {
            "document_title": f"{document_type.replace('_', ' ').title()} - {get_val('insured_name', 'Insured')}",
            "sections": generated_sections,
            "total_placeholders": len(placeholders),
            "ready_for_review": len(placeholders) < 10,
            "draft_notes": f"Document generated using template fallback. {len(placeholders)} placeholders require completion.",
            "_generated_by": "fallback_template"
        }

    def _generate_mrc_slip_sections(self, get_val, placeholders, assessment) -> List[Dict]:
        """Generate Lloyd's MRC Slip sections."""
        sections = []

        # Risk Details
        sections.append({
            "section_name": "risk_details",
            "section_title": "RISK DETAILS",
            "content": f"""UNIQUE MARKET REFERENCE: {get_val('unique_market_reference')}

TYPE: {get_val('coverage_type', get_val('risk_category', '[RISK_CATEGORY]')).upper()} INSURANCE

This slip sets forth the terms and conditions under which the Underwriters identified herein
agree to insure the risk described below.""",
            "is_complete": True,
            "placeholders": []
        })

        # The Assured
        insured = get_val('insured_name')
        address = get_val('insured_address', '[INSURED ADDRESS]')
        if '[' in address:
            placeholders.append('INSURED_ADDRESS')

        sections.append({
            "section_name": "the_assured",
            "section_title": "THE ASSURED",
            "content": f"""Name: {insured}
Address: {address}
Business: {get_val('insured_business', '[BUSINESS DESCRIPTION]')}

And/or as may be more fully described in the Schedule.""",
            "is_complete": '[' not in f"{insured}{address}",
            "placeholders": [p for p in ['INSURED_ADDRESS', 'BUSINESS_DESCRIPTION'] if f'[{p}]' in f"{address}{get_val('insured_business', '')}"]
        })

        # Period
        inception = get_val('inception_date', '[INCEPTION DATE]')
        expiry = get_val('expiry_date', '[EXPIRY DATE]')
        if '[' in inception:
            placeholders.append('INCEPTION_DATE')
        if '[' in expiry:
            placeholders.append('EXPIRY_DATE')

        sections.append({
            "section_name": "period",
            "section_title": "PERIOD",
            "content": f"""From: {inception}
To: {expiry}

Both days inclusive, local standard time at the address of the Assured.

{get_val('period_months', 12)} months from inception unless otherwise stated or cancelled
in accordance with the policy conditions.""",
            "is_complete": '[' not in f"{inception}{expiry}",
            "placeholders": [p for p in ['INCEPTION_DATE', 'EXPIRY_DATE'] if f'[{p.replace("_", " ")}]' in f"{inception}{expiry}"]
        })

        # Interest/Coverage
        sections.append({
            "section_name": "interest",
            "section_title": "INTEREST",
            "content": f"""All risks of physical loss or damage to property of every description belonging to or
held in trust by or for which the Assured is responsible, including but not limited to:

- Buildings, structures and fixtures
- Machinery, plant and equipment
- Stock, materials and goods in trade
- Computer equipment, software and data
- Business interruption and loss of profits

As more fully described in the policy wording.""",
            "is_complete": True,
            "placeholders": []
        })

        # Territorial Limits
        territory = get_val('territory', '[TERRITORIAL LIMITS]')
        sections.append({
            "section_name": "territorial_limits",
            "section_title": "TERRITORIAL LIMITS",
            "content": f"""{territory}

Including transit to and from all locations within the territorial limits.""",
            "is_complete": '[' not in territory,
            "placeholders": ['TERRITORIAL_LIMITS'] if '[' in territory else []
        })

        # Sum Insured / Limit
        sum_insured = get_val('sum_insured', '[SUM INSURED]')
        sections.append({
            "section_name": "limit_of_liability",
            "section_title": "LIMIT OF LIABILITY / SUM INSURED",
            "content": f"""Total Sum Insured: {sum_insured}

In the aggregate for all losses arising during the period of insurance.

Subject to the following sub-limits:
- As per policy schedule""",
            "is_complete": '[' not in sum_insured,
            "placeholders": ['SUM_INSURED'] if '[' in sum_insured else []
        })

        # Deductible
        deductible = get_val('deductible', '[DEDUCTIBLE AMOUNT]')
        sections.append({
            "section_name": "deductible",
            "section_title": "DEDUCTIBLE",
            "content": f"""Each and every loss: {deductible}

The Deductible shall apply to each and every claim or series of claims arising from
one event or occurrence.""",
            "is_complete": '[' not in deductible,
            "placeholders": ['DEDUCTIBLE_AMOUNT'] if '[' in deductible else []
        })

        # Premium
        premium = get_val('premium', '[PREMIUM AMOUNT]')
        sections.append({
            "section_name": "premium",
            "section_title": "PREMIUM",
            "content": f"""Annual Premium: {premium}

Plus Insurance Premium Tax at the prevailing rate where applicable.

Minimum and Deposit Premium: 100% of the above premium.
Premium Payment: Within 60 days of inception or as per credit terms.""",
            "is_complete": '[' not in premium,
            "placeholders": ['PREMIUM_AMOUNT'] if '[' in premium else []
        })

        # Conditions
        sections.append({
            "section_name": "conditions_precedent",
            "section_title": "CONDITIONS PRECEDENT TO LIABILITY",
            "content": """1. Premium payment within the credit period specified
2. Observance of all warranties and conditions
3. Maintenance of adequate protection devices as specified
4. Compliance with all statutory and regulatory requirements
5. Immediate notification of any material change in risk""",
            "is_complete": True,
            "placeholders": []
        })

        # Exclusions
        sections.append({
            "section_name": "exclusions",
            "section_title": "EXCLUSIONS",
            "content": """This insurance does not cover:

1. War, civil war, revolution, rebellion, insurrection
2. Nuclear reaction, radiation or radioactive contamination
3. Terrorism (unless specifically included)
4. Cyber attack (unless specifically included)
5. Wear and tear, gradual deterioration
6. Inherent defect or latent defect
7. Consequential loss (unless specifically included)
8. Pollution and contamination (unless sudden and accidental)
9. Contractual liability
10. Intentional acts by the Assured

Subject to the full exclusions set out in the policy wording.""",
            "is_complete": True,
            "placeholders": []
        })

        # Jurisdiction
        sections.append({
            "section_name": "jurisdiction",
            "section_title": "JURISDICTION AND GOVERNING LAW",
            "content": """This insurance shall be governed by and construed in accordance with the laws of
England and Wales. Any dispute arising out of or in connection with this insurance
shall be subject to the exclusive jurisdiction of the English courts.""",
            "is_complete": True,
            "placeholders": []
        })

        # Several Liability
        sections.append({
            "section_name": "several_liability",
            "section_title": "SEVERAL LIABILITY",
            "content": """The liability of an Underwriter under this contract is several and not joint with other
Underwriters party to this contract. An Underwriter is liable only for the proportion of
liability it has underwritten. An Underwriter is not jointly liable for the proportion of
liability underwritten by any other Underwriter.

In the event any Underwriter does not pay, the other Underwriters are not responsible
for any unpaid amounts.""",
            "is_complete": True,
            "placeholders": []
        })

        # Security
        sections.append({
            "section_name": "security",
            "section_title": "SECURITY",
            "content": f"""SLIP LEADER: [LEAD SYNDICATE] - [LEAD LINE]%

FOLLOWING MARKETS: [TO BE ADVISED]

BROKER: {get_val('broker_name', '[BROKER NAME]')}
BROKER REFERENCE: {get_val('broker_reference', '[BROKER REFERENCE]')}

_______________________________________________
For and on behalf of Lloyd's Underwriters
Date: {get_val('generation_date')}""",
            "is_complete": False,
            "placeholders": ['LEAD_SYNDICATE', 'LEAD_LINE', 'FOLLOWING_MARKETS', 'BROKER_NAME', 'BROKER_REFERENCE']
        })

        return sections

    def _generate_policy_wording_sections(self, get_val, placeholders, assessment) -> List[Dict]:
        """Generate Lloyd's Policy Wording sections."""
        sections = []

        sections.append({
            "section_name": "declarations",
            "section_title": "DECLARATIONS",
            "content": f"""POLICY NUMBER: {get_val('unique_market_reference')}

NAMED INSURED: {get_val('insured_name')}

MAILING ADDRESS: {get_val('insured_address', '[INSURED ADDRESS]')}

POLICY PERIOD: From {get_val('inception_date', '[INCEPTION DATE]')} to {get_val('expiry_date', '[EXPIRY DATE]')}
               Both days inclusive at 12:01 A.M. local time at the address of the Named Insured

LIMIT OF INSURANCE: {get_val('sum_insured')}

DEDUCTIBLE: {get_val('deductible', '[DEDUCTIBLE]')}

PREMIUM: {get_val('premium')}

FORMS AND ENDORSEMENTS: As attached to and forming part of this policy""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "insuring_agreements",
            "section_title": "INSURING AGREEMENTS",
            "content": f"""SECTION I - PROPERTY COVERAGE

A. COVERED PROPERTY
   Subject to all terms, conditions and exclusions of this Policy, we will pay for direct
   physical loss of or damage to Covered Property caused by a Covered Cause of Loss.

B. COVERED CAUSES OF LOSS
   This policy covers risks of direct physical loss or damage to Covered Property from
   any cause except those causes excluded.

C. COVERAGE TERRITORY
   This insurance applies to Covered Property located within:
   {get_val('territory', '[TERRITORIAL LIMITS]')}

SECTION II - BUSINESS INTERRUPTION COVERAGE (IF APPLICABLE)

   Subject to all terms, conditions and exclusions of this Policy, we will pay for the
   actual loss of Business Income sustained due to the necessary suspension of operations
   during the Period of Restoration caused by direct physical loss or damage to property
   at the described premises.""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "definitions",
            "section_title": "DEFINITIONS",
            "content": """For purposes of this Policy, the following definitions apply:

"Covered Property" means:
   a) Buildings at the described premises
   b) Business Personal Property at the described premises
   c) Personal Property of others in the Insured's care, custody or control

"Covered Cause of Loss" means direct physical loss or damage unless excluded.

"Business Income" means the net income that would have been earned plus continuing
normal operating expenses including payroll.

"Period of Restoration" means the period of time that begins 72 hours after the time
of direct physical loss or damage and ends on the earlier of the date when the
property should be repaired or replaced with reasonable speed and similar quality,
or the date when business is resumed at a new permanent location.

"Occurrence" means any one accident or event, or series of accidents or events
arising out of one original cause.""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "exclusions",
            "section_title": "EXCLUSIONS",
            "content": """This insurance does not apply to:

A. EXCLUDED CAUSES OF LOSS
   1. War, invasion, act of foreign enemies, hostilities
   2. Civil war, rebellion, revolution, insurrection
   3. Nuclear reaction, radiation, radioactive contamination
   4. Terrorism (unless coverage is specifically included)
   5. Cyber attack (unless coverage is specifically included)

B. EXCLUDED LOSSES
   1. Loss or damage caused by wear and tear, deterioration
   2. Loss or damage caused by inherent defect
   3. Loss or damage caused by insects, vermin, rodents
   4. Loss or damage caused by settling, cracking, shrinking
   5. Consequential loss of any kind (unless specifically covered)

C. EXCLUDED PROPERTY
   1. Currency, money, securities, valuable papers
   2. Vehicles licensed for road use
   3. Property more specifically insured
   4. Underground pipes, flues, drains""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "conditions",
            "section_title": "CONDITIONS",
            "content": """A. DUTIES IN THE EVENT OF LOSS
   In case of loss, the Insured must:
   1. Give prompt notice to us or our agent
   2. Protect the property from further damage
   3. Cooperate with us in the investigation
   4. Submit to examination under oath
   5. Produce records as we reasonably request
   6. File a detailed proof of loss within 60 days

B. VALUATION
   Property shall be valued at actual cash value at the time of loss, or at the
   cost of repair or replacement with material of like kind and quality.

C. LOSS PAYMENT
   We will pay the amount of loss within 30 days after we receive an acceptable
   proof of loss and the amount of loss is agreed upon.

D. SUBROGATION
   If we pay for a loss, we may require you to assign to us your right of recovery
   against others.""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "claims",
            "section_title": "CLAIMS",
            "content": """CLAIMS NOTIFICATION
All claims must be notified to:

Lloyd's Claims Office
[CLAIMS CONTACT DETAILS]

Telephone: [CLAIMS TELEPHONE]
Email: [CLAIMS EMAIL]

Claims should be reported as soon as reasonably practicable and in any event
within [30] days of the Insured becoming aware of any incident likely to give
rise to a claim.

CLAIMS COOPERATION
The Insured shall:
a) Give all reasonable assistance in pursuing recovery against third parties
b) Not admit liability without our prior written consent
c) Take all reasonable steps to minimize the loss
d) Preserve all damaged property for inspection""",
            "is_complete": False,
            "placeholders": ['CLAIMS_CONTACT_DETAILS', 'CLAIMS_TELEPHONE', 'CLAIMS_EMAIL']
        })

        sections.append({
            "section_name": "general_provisions",
            "section_title": "GENERAL PROVISIONS",
            "content": """A. ASSIGNMENT
   Your rights under this policy may not be transferred without our written consent.

B. CHANGES
   This policy contains all agreements between you and us. Its terms may be amended
   only by endorsement issued by us.

C. CANCELLATION
   This policy may be cancelled by either party giving 30 days written notice.

D. CURRENCY
   All amounts are stated and payable in the currency shown in the Declarations.

E. GOVERNING LAW
   This Policy shall be governed by and construed in accordance with the laws of
   England and Wales.

F. ARBITRATION
   Any dispute shall first be referred to arbitration in London in accordance
   with the Arbitration Act 1996.""",
            "is_complete": True,
            "placeholders": []
        })

        return sections

    def _generate_cover_note_sections(self, get_val, placeholders, assessment) -> List[Dict]:
        """Generate Lloyd's Cover Note sections."""
        sections = []

        sections.append({
            "section_name": "header",
            "section_title": "Lloyd's Cover Note",
            "content": f"""LLOYD'S UNDERWRITERS' ASSOCIATION

COVER NOTE

This Cover Note is issued in accordance with the authority granted to the undersigned
Coverholder under Binding Authority Agreement Number [BINDING_AUTHORITY_NUMBER]""",
            "is_complete": False,
            "placeholders": ['BINDING_AUTHORITY_NUMBER']
        })

        sections.append({
            "section_name": "cover_note_reference",
            "section_title": "Cover Note Reference",
            "content": f"""{get_val('reference_number')}

Broker Reference: {get_val('broker_reference', '[BROKER_REFERENCE]')}""",
            "is_complete": get_val('broker_reference') is not None,
            "placeholders": [] if get_val('broker_reference') else ['BROKER_REFERENCE']
        })

        decision = get_val('decision', 'PENDING')
        status_text = "approved" if decision == "GO" else "referred for further underwriting review" if decision == "REFER" else "pending final approval"

        sections.append({
            "section_name": "status_declaration",
            "section_title": "Status Declaration",
            "content": f"""IMPORTANT: This Cover Note is issued pending full underwriting approval.
Cover is provided on a {status_text} basis and is conditional upon final approval
by the Lead Underwriter.

Decision Status: {decision}
Risk Score: {get_val('risk_score', 'N/A')}""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "insured_details",
            "section_title": "Insured Details",
            "content": f"""Name: {get_val('insured_name')}

Address: {get_val('insured_address', '[INSURED_ADDRESS]')}

Business Description: {get_val('insured_business', '[BUSINESS_DESCRIPTION]')}""",
            "is_complete": get_val('insured_address') is not None,
            "placeholders": [p for p in ['INSURED_ADDRESS', 'BUSINESS_DESCRIPTION']
                           if get_val('insured_address') is None or get_val('insured_business') is None]
        })

        sections.append({
            "section_name": "coverage_period",
            "section_title": "Period of Insurance",
            "content": f"""Inception Date: {get_val('inception_date', '[INCEPTION_DATE]')}

Expiry Date: {get_val('expiry_date', '[EXPIRY_DATE]')}

{get_val('period_months', 12)} months from inception unless otherwise stated or cancelled
in accordance with the policy terms.""",
            "is_complete": get_val('inception_date') is not None and get_val('expiry_date') is not None,
            "placeholders": [p for p in ['INCEPTION_DATE', 'EXPIRY_DATE']
                           if get_val('inception_date') is None or get_val('expiry_date') is None]
        })

        sections.append({
            "section_name": "coverage_details",
            "section_title": "Coverage Details",
            "content": f"""Risk Category: {get_val('risk_category', '[RISK_CATEGORY]')} Insurance

Sum Insured: {get_val('sum_insured')}

The Insured is covered for physical loss of or damage to property as detailed in the
underlying policy terms and conditions, subject to all terms, conditions, exclusions,
and warranties therein.""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "territory",
            "section_title": "Territory",
            "content": f"""Coverage applies within the following territories:

{get_val('territory', '[TERRITORIAL_LIMITS]')}""",
            "is_complete": get_val('territory') is not None,
            "placeholders": [] if get_val('territory') else ['TERRITORIAL_LIMITS']
        })

        sections.append({
            "section_name": "premium",
            "section_title": "Premium",
            "content": f"""Total Premium: {get_val('premium')}

Premium Payment Terms: [PREMIUM_PAYMENT_TERMS]

This premium is subject to adjustment based on the final underwriting terms and
any additional information received.""",
            "is_complete": False,
            "placeholders": ['PREMIUM_PAYMENT_TERMS']
        })

        sections.append({
            "section_name": "deductibles",
            "section_title": "Deductibles/Excess",
            "content": f"""Deductibles: {get_val('deductible', 'To be confirmed upon final underwriting approval.')}

Specific deductibles will be detailed in the final policy documentation.""",
            "is_complete": get_val('deductible') is not None,
            "placeholders": [] if get_val('deductible') else ['DEDUCTIBLE']
        })

        sections.append({
            "section_name": "exclusions",
            "section_title": "Standard Exclusions",
            "content": """This insurance does not cover:

1. War, civil war, revolution, rebellion, insurrection, or hostile acts
2. Nuclear reaction, nuclear radiation, or radioactive contamination
3. Malicious acts by the Insured or any person acting on their behalf
4. Consequential loss of any kind (unless specifically covered)
5. Wear and tear, gradual deterioration, or inherent defect
6. Damage caused by insects, vermin, or rodents
7. Terrorism (unless specifically agreed and noted herein)""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "claims_notification",
            "section_title": "Claims Notification",
            "content": """All claims must be reported immediately to:

Lloyd's Claims Office
[CLAIMS_CONTACT_DETAILS]

In the event of loss or damage, the Insured must:
1. Take all reasonable steps to prevent further damage
2. Notify the police if the loss involves a criminal act
3. Preserve all damaged property for inspection
4. Provide full details of the loss within 30 days""",
            "is_complete": False,
            "placeholders": ['CLAIMS_CONTACT_DETAILS']
        })

        sections.append({
            "section_name": "lead_underwriter",
            "section_title": "Lead Underwriter",
            "content": f"""Lead Syndicate: [LEAD_SYNDICATE]

Lead Underwriter: [LEAD_UNDERWRITER_NAME]

Supporting Syndicates: [SUPPORTING_SYNDICATES]""",
            "is_complete": False,
            "placeholders": ['LEAD_SYNDICATE', 'LEAD_UNDERWRITER_NAME', 'SUPPORTING_SYNDICATES']
        })

        sections.append({
            "section_name": "coverholder_details",
            "section_title": "Coverholder Declaration",
            "content": f"""This Cover Note is issued by:

Coverholder Name: [COVERHOLDER_NAME]

Address: [COVERHOLDER_ADDRESS]

Date of Issue: {get_val('generation_date')}

Authorised Signature: __________________________

Name: [SIGNATORY_NAME]

Position: [SIGNATORY_POSITION]""",
            "is_complete": False,
            "placeholders": ['COVERHOLDER_NAME', 'COVERHOLDER_ADDRESS', 'SIGNATORY_NAME', 'SIGNATORY_POSITION']
        })

        sections.append({
            "section_name": "governing_law",
            "section_title": "Governing Law and Jurisdiction",
            "content": """This Cover Note shall be governed by and construed in accordance with the laws of
England and Wales. Any dispute arising out of or in connection with this Cover Note
shall be subject to the exclusive jurisdiction of the English courts.""",
            "is_complete": True,
            "placeholders": []
        })

        return sections

    def _generate_quote_sections(self, get_val, placeholders, assessment) -> List[Dict]:
        """Generate Lloyd's Quote sections."""
        sections = []

        sections.append({
            "section_name": "header",
            "section_title": "Lloyd's Quotation",
            "content": f"""LLOYD'S OF LONDON
INDICATION / QUOTATION

This quotation is provided for indication purposes and does not constitute a binding
offer of insurance.""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "reference",
            "section_title": "Reference",
            "content": f"""Quote Reference: {get_val('reference_number')}
Date: {get_val('generation_date')}
Validity: 30 days from date of issue""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "insured",
            "section_title": "Proposed Insured",
            "content": f"""Name: {get_val('insured_name')}
Address: {get_val('insured_address', '[INSURED_ADDRESS]')}
Business: {get_val('insured_business', '[BUSINESS_DESCRIPTION]')}""",
            "is_complete": get_val('insured_address') is not None,
            "placeholders": [p for p in ['INSURED_ADDRESS', 'BUSINESS_DESCRIPTION']
                           if get_val('insured_address') is None]
        })

        sections.append({
            "section_name": "coverage_summary",
            "section_title": "Coverage Summary",
            "content": f"""Type: {get_val('coverage_type', get_val('risk_category', '[RISK_CATEGORY]'))} Insurance
Territory: {get_val('territory', '[TERRITORIAL_LIMITS]')}
Period: {get_val('period_months', 12)} months
Sum Insured: {get_val('sum_insured')}""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "premium_indication",
            "section_title": "Premium Indication",
            "content": f"""Indicated Premium: {get_val('premium')}
Plus Insurance Premium Tax where applicable.

This premium indication is subject to:
- Full underwriting review
- Satisfactory completion of proposal form
- No material change in risk
- Standard terms and conditions""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "terms_and_conditions",
            "section_title": "Subject To",
            "content": """This quotation is subject to:

1. Satisfactory review of full submission documents
2. Completion of underwriting questionnaire
3. No material adverse claims history
4. Compliance with minimum security requirements
5. Standard Lloyd's policy terms and conditions
6. Deductibles as may be agreed""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "validity",
            "section_title": "Validity",
            "content": f"""This quotation is valid for 30 days from {get_val('generation_date')}.

After this date, terms may be subject to review and adjustment.""",
            "is_complete": True,
            "placeholders": []
        })

        sections.append({
            "section_name": "next_steps",
            "section_title": "Next Steps",
            "content": """To proceed with this quotation:

1. Review the terms and conditions
2. Complete and return the proposal form
3. Provide any additional information requested
4. Confirm acceptance of terms

Contact your Lloyd's broker to proceed.""",
            "is_complete": True,
            "placeholders": []
        })

        return sections

    def _generate_property_policy_sections(self, get_val, placeholders, assessment) -> List[Dict]:
        """Generate Property Policy sections."""
        sections = []

        # Header/Declarations
        sections.append({
            "section_name": "declarations",
            "section_title": "POLICY DECLARATIONS",
            "content": f"""PROPERTY INSURANCE POLICY

Policy Number: {get_val('unique_market_reference', get_val('reference_number', '[POLICY NUMBER]'))}

NAMED INSURED: {get_val('insured_name')}

MAILING ADDRESS: {get_val('insured_address', '[INSURED ADDRESS]')}

POLICY PERIOD:
From: {get_val('inception_date', '[INCEPTION DATE]')} at 12:01 A.M.
To: {get_val('expiry_date', '[EXPIRY DATE]')} at 12:01 A.M.
(Local Standard Time at the address of the Named Insured)

LIMITS OF INSURANCE: {get_val('sum_insured', '[SUM INSURED]')}

DEDUCTIBLE: {get_val('deductible', '[DEDUCTIBLE]')} each occurrence

PREMIUM: {get_val('premium', '[PREMIUM]')}

COVERAGE TERRITORY: {get_val('territory', '[TERRITORY]')}

IN WITNESS WHEREOF, the Insurers have caused this Policy to be signed.""",
            "is_complete": True,
            "placeholders": []
        })

        # Insuring Agreement
        sections.append({
            "section_name": "insuring_agreement",
            "section_title": "INSURING AGREEMENT",
            "content": f"""SECTION 1 - PROPERTY COVERAGE

A. COVERED PROPERTY
   We will pay for direct physical loss of or damage to Covered Property at the premises
   described in the Declarations caused by a Covered Cause of Loss.

   1. Covered Property includes:
      a) Buildings as described in the Declarations, including:
         - Completed additions
         - Fixtures, including outdoor fixtures
         - Permanently installed machinery and equipment
         - Personal property owned by you that is used to maintain or service the buildings

      b) Business Personal Property located in or on the buildings or in the open within
         100 feet of the described premises:
         - Furniture and fixtures
         - Machinery and equipment
         - Stock and inventory
         - All other personal property owned by you and used in your business
         - Labor, materials or services furnished or arranged by you on personal property
           of others

B. COVERED CAUSES OF LOSS
   This policy insures against risks of direct physical loss or damage from any cause except
   those causes specifically excluded.

C. ADDITIONAL COVERAGES
   1. Debris Removal
   2. Preservation of Property
   3. Fire Department Service Charge
   4. Pollutant Clean Up and Removal
   5. Increased Cost of Construction""",
            "is_complete": True,
            "placeholders": []
        })

        # Business Interruption
        sections.append({
            "section_name": "business_interruption",
            "section_title": "BUSINESS INTERRUPTION COVERAGE",
            "content": f"""SECTION 2 - BUSINESS INTERRUPTION

A. COVERAGE
   We will pay for the actual loss of Business Income you sustain due to the necessary
   suspension of your operations during the period of restoration.

   1. Business Income means the:
      a) Net Income (Net Profit or Loss before income taxes) that would have been earned
         or incurred; and
      b) Continuing normal operating expenses incurred, including payroll.

   2. Period of Restoration means the period of time that:
      a) Begins with the date of direct physical loss or damage caused by a Covered Cause
         of Loss; and
      b) Ends on the date when the property should be repaired, rebuilt or replaced with
         reasonable speed and similar quality.

B. EXTRA EXPENSE
   We will pay the Extra Expense you incur during the period of restoration to:
   1. Avoid or minimize the suspension of business and to continue operations
   2. Minimize the suspension of business if operations cannot continue

   Indemnity Period: {get_val('indemnity_period', '12 months')}""",
            "is_complete": True,
            "placeholders": []
        })

        # Exclusions
        sections.append({
            "section_name": "exclusions",
            "section_title": "EXCLUSIONS",
            "content": """SECTION 3 - EXCLUSIONS

We will not pay for loss or damage caused directly or indirectly by any of the following:

A. GENERAL EXCLUSIONS
   1. War and Military Action
   2. Nuclear Hazard
   3. Government Action
   4. Power Failure (originating off premises)
   5. Ordinance or Law
   6. Earth Movement (unless specifically endorsed)
   7. Water (flood, surface water, tidal wave)
   8. Contamination or Pollution

B. PROPERTY EXCLUSIONS
   1. Accounts, bills, currency, deeds, evidence of debt, money
   2. Animals
   3. Automobiles, aircraft, watercraft (unless stock)
   4. Bridges, roadways, walks, patios
   5. Growing crops and lawns
   6. Land (including land on which property is located)
   7. Personal property while airborne or waterborne
   8. Underground pipes, flues or drains

C. CAUSE OF LOSS EXCLUSIONS
   1. Wear and tear, deterioration, inherent vice
   2. Insects, birds, rodents, vermin
   3. Settling, cracking, shrinking, bulging
   4. Mechanical breakdown
   5. Dampness or dryness of atmosphere
   6. Changes in temperature
   7. Marring, scratching
   8. Voluntary parting with property""",
            "is_complete": True,
            "placeholders": []
        })

        # Conditions
        sections.append({
            "section_name": "conditions",
            "section_title": "CONDITIONS",
            "content": """SECTION 4 - CONDITIONS

A. GENERAL CONDITIONS
   1. CONCEALMENT, MISREPRESENTATION OR FRAUD
      This policy is void if you have intentionally concealed or misrepresented any material
      fact or circumstance concerning this insurance.

   2. POLICY PERIOD, COVERAGE TERRITORY
      Under this policy we cover loss or damage commencing during the policy period shown
      in the Declarations within the coverage territory.

   3. OTHER INSURANCE
      If there is other insurance covering the same loss or damage, we will pay only our
      share of the loss.

   4. DUTIES IN THE EVENT OF LOSS OR DAMAGE
      a) Notify the police if a law may have been broken
      b) Give us prompt notice of the loss or damage
      c) Protect the property from further damage
      d) Cooperate with us in the investigation
      e) Prepare an inventory of damaged property
      f) Provide records and documents as requested
      g) Submit to examination under oath

   5. LOSS PAYMENT
      We will pay for covered loss or damage within 30 days after receiving your sworn
      proof of loss and reaching agreement with you.

   6. RECOVERED PROPERTY
      If either you or we recover any property after loss settlement, that party must give
      the other prompt notice.

   7. VACANCY
      If the building where loss or damage occurs has been vacant for more than 60
      consecutive days before that loss or damage occurs, we will not pay for any loss
      or damage caused by vandalism, sprinkler leakage, building glass breakage, water
      damage, theft or attempted theft.

   8. MORTGAGEHOLDERS
      Loss or damage, if any, shall be payable to any mortgageholder named in the
      Declarations.""",
            "is_complete": True,
            "placeholders": []
        })

        # Valuation
        sections.append({
            "section_name": "valuation",
            "section_title": "VALUATION",
            "content": """SECTION 5 - VALUATION

A. PROPERTY VALUATION
   1. BUILDINGS
      At replacement cost (without deduction for depreciation) of that part of the building
      damaged with material of like kind and quality.

   2. BUSINESS PERSONAL PROPERTY
      a) Stock: at selling price less discounts and expenses
      b) All other property: replacement cost new

B. REPLACEMENT COST CONDITION
   You may make claim for loss or damage on a replacement cost basis only if:
   1. You repair or replace the damaged property; and
   2. The repair or replacement is made as soon as reasonably possible after the loss.

C. AGREED VALUE
   If the Declarations shows Agreed Value, the amount shown in the Declarations for each
   category of property is the agreed amount of insurance for that category.""",
            "is_complete": True,
            "placeholders": []
        })

        # Signature
        sections.append({
            "section_name": "signature",
            "section_title": "AUTHORIZATION",
            "content": f"""IN WITNESS WHEREOF, this Policy has been signed by the Insurers' authorized representative.

Policy Effective Date: {get_val('inception_date', '[EFFECTIVE DATE]')}

Underwriting Reference: {get_val('broker_reference', '[BROKER REFERENCE]')}

_________________________________
Authorized Representative

_________________________________
Date

This policy is issued subject to Lloyd's regulations and the terms and conditions of the
standard Lloyd's policy form.""",
            "is_complete": True,
            "placeholders": []
        })

        return sections

    def _generate_certificate_sections(self, get_val, placeholders, assessment) -> List[Dict]:
        """Generate Certificate of Insurance sections."""
        sections = []

        from datetime import datetime
        current_date = datetime.now().strftime('%d %B %Y')

        # Header
        sections.append({
            "section_name": "header",
            "section_title": "CERTIFICATE OF INSURANCE",
            "content": f"""LLOYD'S OF LONDON
CERTIFICATE OF INSURANCE

Certificate Number: COI-{get_val('reference_number', '[CERT NUMBER]')}
Issue Date: {current_date}

This Certificate is issued as a matter of information only and confers no rights upon the
Certificate Holder. This Certificate does not amend, extend or alter the coverage afforded
by the policies listed below.

This Certificate of Insurance certifies that the policies of insurance listed below have
been issued to the Insured named below for the policy period indicated.""",
            "is_complete": True,
            "placeholders": []
        })

        # Producer/Broker
        sections.append({
            "section_name": "producer",
            "section_title": "PRODUCER/BROKER",
            "content": f"""PRODUCER:
Broker Reference: {get_val('broker_reference', '[BROKER REFERENCE]')}

Contact: [Broker Contact Details]
Address: [Broker Address]
Telephone: [Broker Telephone]
Email: [Broker Email]""",
            "is_complete": False,
            "placeholders": ['BROKER_CONTACT', 'BROKER_ADDRESS', 'BROKER_TELEPHONE', 'BROKER_EMAIL']
        })

        # Insured Details
        sections.append({
            "section_name": "insured",
            "section_title": "INSURED",
            "content": f"""NAMED INSURED:
{get_val('insured_name')}

ADDRESS:
{get_val('insured_address', '[INSURED ADDRESS]')}

The insurance afforded by the policies described herein is subject to all the terms,
exclusions and conditions of such policies.""",
            "is_complete": '[' not in get_val('insured_address', '['),
            "placeholders": ['INSURED_ADDRESS'] if '[' in get_val('insured_address', '[') else []
        })

        # Coverage Details
        risk_category = get_val('risk_category', 'PROPERTY')
        sections.append({
            "section_name": "coverages",
            "section_title": "COVERAGES",
            "content": f"""TYPE OF INSURANCE: {risk_category.upper() if isinstance(risk_category, str) else 'PROPERTY'} INSURANCE

POLICY NUMBER: {get_val('unique_market_reference', get_val('reference_number', '[POLICY NUMBER]'))}

POLICY PERIOD:
Effective Date: {get_val('inception_date', '[INCEPTION DATE]')}
Expiration Date: {get_val('expiry_date', '[EXPIRY DATE]')}

LIMITS OF LIABILITY:
Total Sum Insured: {get_val('sum_insured', '[SUM INSURED]')}

Per Occurrence Limit: {get_val('sum_insured', '[SUM INSURED]')}
Aggregate Limit: {get_val('sum_insured', '[SUM INSURED]')}

DEDUCTIBLE: {get_val('deductible', '[DEDUCTIBLE]')}

PREMIUM: {get_val('premium', '[PREMIUM]')}

TERRITORY: {get_val('territory', '[TERRITORY]')}""",
            "is_complete": True,
            "placeholders": []
        })

        # Description of Operations
        sections.append({
            "section_name": "description",
            "section_title": "DESCRIPTION OF OPERATIONS/LOCATIONS/VEHICLES",
            "content": f"""LOCATIONS COVERED:
{get_val('territory', '[TERRITORY]')}

DESCRIPTION OF OPERATIONS:
Insurance is provided for the operations of the Named Insured as declared in the
underlying policy schedule and proposal documentation.

SPECIAL CONDITIONS:
Subject to all terms, conditions, warranties and exclusions of the underlying policy.

Additional Interests: As per policy schedule.""",
            "is_complete": True,
            "placeholders": []
        })

        # Certificate Holder
        sections.append({
            "section_name": "certificate_holder",
            "section_title": "CERTIFICATE HOLDER",
            "content": """CERTIFICATE HOLDER:

[CERTIFICATE HOLDER NAME]
[CERTIFICATE HOLDER ADDRESS]

The Certificate Holder is named as an interested party for information purposes only.
This Certificate does not confer any rights or obligations on the Certificate Holder.""",
            "is_complete": False,
            "placeholders": ['CERTIFICATE_HOLDER_NAME', 'CERTIFICATE_HOLDER_ADDRESS']
        })

        # Cancellation Notice
        sections.append({
            "section_name": "cancellation",
            "section_title": "CANCELLATION",
            "content": """SHOULD ANY OF THE ABOVE DESCRIBED POLICIES BE CANCELLED BEFORE THE EXPIRATION DATE
THEREOF, NOTICE WILL BE DELIVERED IN ACCORDANCE WITH THE POLICY PROVISIONS.

Standard cancellation terms apply as per policy conditions. Typically 30 days written
notice for cancellation by the Insurer, except 10 days for non-payment of premium.""",
            "is_complete": True,
            "placeholders": []
        })

        # Authorization
        sections.append({
            "section_name": "authorization",
            "section_title": "AUTHORIZATION",
            "content": f"""This Certificate is issued by the undersigned as a matter of information and is
subject to all terms, conditions and exclusions of the policy to which it refers.

AUTHORIZED REPRESENTATIVE:

_________________________________
Signature

_________________________________
Name: [AUTHORIZED SIGNATORY]

_________________________________
Date: {current_date}

Certificate issued on behalf of Certain Underwriters at Lloyd's, London.""",
            "is_complete": False,
            "placeholders": ['AUTHORIZED_SIGNATORY']
        })

        return sections

    def _get_lma_clauses_for_category(self, risk_category: str) -> List[Dict[str, Any]]:
        """
        Get recommended LMA clauses based on risk category.
        Always includes core clauses and sanctions clauses.
        """
        clauses = []

        # Always add core clauses
        for clause in LMA_CLAUSES_BY_CATEGORY.get("_core", []):
            clauses.append({
                **clause,
                "selected": clause.get("mandatory", False),
                "reason": "Standard Lloyd's market requirement"
            })

        # Add category-specific clauses
        category_key = risk_category.lower() if risk_category else "property"
        # Map common risk categories
        category_mapping = {
            "marine_cargo": "marine",
            "marine cargo": "marine",
            "professional_indemnity": "professional",
            "professional indemnity": "professional",
            "cyber_liability": "cyber",
            "cyber liability": "cyber",
            "general_liability": "casualty",
            "general liability": "casualty",
            "property_damage": "property",
            "financial_lines": "professional",
        }
        category_key = category_mapping.get(category_key, category_key)

        for clause in LMA_CLAUSES_BY_CATEGORY.get(category_key, []):
            clauses.append({
                **clause,
                "selected": clause.get("mandatory", False),
                "reason": f"Recommended for {risk_category or 'this risk'}"
            })

        # Always add sanctions clauses
        for clause in LMA_CLAUSES_BY_CATEGORY.get("_sanctions", []):
            clauses.append({
                **clause,
                "selected": True,  # Sanctions always pre-selected
                "reason": "Sanctions compliance requirement"
            })

        return clauses

    def _calculate_document_confidence(
        self,
        document_type: str,
        assessment: Dict[str, Any],
        is_mandatory: bool
    ) -> float:
        """
        Calculate AI confidence for a document based on assessment data.
        Higher confidence = more certain this document is needed.
        """
        base_confidence = 0.90 if is_mandatory else 0.75

        risk_category = assessment.get("risk_category", "").lower()
        decision = assessment.get("decision", "").lower() if assessment.get("decision") else ""
        risk_score = assessment.get("risk_score") or 50
        sum_insured = assessment.get("sum_insured") or 0
        ai_analysis = assessment.get("ai_analysis") or {}

        # Increase confidence for essential documents
        if document_type == "lloyds_mrc_slip":
            base_confidence = 0.98  # Almost always needed for Lloyd's
        elif document_type == "certificate_of_insurance":
            base_confidence = 0.95 if decision == "go" else 0.80

        # Risk category alignment
        category_document_map = {
            "marine": ["marine_cargo", "bill_of_lading"],
            "cyber": ["cyber_liability", "data_breach_response"],
            "property": ["property_policy", "schedule_of_locations"],
            "professional": ["professional_indemnity"],
            "aviation": ["aviation_policy"],
            "casualty": ["general_liability_policy"],
        }

        for category, docs in category_document_map.items():
            if category in risk_category and document_type in docs:
                base_confidence = min(0.98, base_confidence + 0.10)

        # High-value risks get more documentation
        if sum_insured and sum_insured > 10000000:
            base_confidence = min(0.99, base_confidence + 0.05)

        # GO decisions increase confidence
        if decision == "go":
            base_confidence = min(0.99, base_confidence + 0.05)

        # High risk scores suggest more documentation
        if risk_score > 70:
            base_confidence = min(0.99, base_confidence + 0.03)

        # AI analysis completeness
        if ai_analysis and isinstance(ai_analysis, dict):
            if ai_analysis.get("summary") and ai_analysis.get("risk_factors"):
                base_confidence = min(0.99, base_confidence + 0.02)

        return round(base_confidence, 2)

    async def suggest_documents(
        self,
        assessment: Dict[str, Any],
        progress_callback: Callable = None
    ) -> Dict[str, Any]:
        """
        Analyze assessment and suggest documents to generate.
        Returns document suggestions AND LMA clause suggestions without generating.
        """
        job_id = str(uuid.uuid4())[:8]
        progress = DocumentGenerationProgress(job_id)
        risk_category = assessment.get("risk_category")

        try:
            progress.start_agent("DocumentRequirementAnalyzer", "Analyzing assessment for document requirements...")
            progress.update_progress(10)
            if progress_callback:
                await progress_callback(progress.to_dict())

            assessment_summary = self._build_assessment_summary(assessment)
            requirements = await self._analyze_requirements(assessment_summary, progress)

            progress.complete_agent(json.dumps(requirements)[:200] if requirements else None)
            progress.update_progress(100)

            # Get LMA clauses based on risk category
            lma_clauses = self._get_lma_clauses_for_category(risk_category)

            # Enhance document suggestions with AI-calculated confidence
            suggested_docs = requirements.get("required_documents", [])
            for doc in suggested_docs:
                if not doc.get("confidence") or doc.get("confidence") == 0:
                    doc["confidence"] = self._calculate_document_confidence(
                        doc.get("document_type", ""),
                        assessment,
                        doc.get("mandatory", False)
                    )

            return {
                "job_id": job_id,
                "assessment_id": assessment.get("id"),
                "risk_category": risk_category,
                "decision": assessment.get("decision"),
                "suggested_documents": suggested_docs,
                "bundle_name": requirements.get("bundle_name", "Document Bundle"),
                "total_estimated_time_seconds": len(suggested_docs) * 30,
                "special_considerations": requirements.get("special_considerations", []),
                "lma_clauses": lma_clauses,
                "progress": progress.to_dict()
            }

        except Exception as e:
            logger.error(f"Document suggestion error: {e}")
            progress.fail_agent(str(e))
            # Even on error, return LMA clauses based on risk category
            lma_clauses = self._get_lma_clauses_for_category(risk_category)
            return {
                "job_id": job_id,
                "error": str(e),
                "lma_clauses": lma_clauses,
                "progress": progress.to_dict()
            }

    async def generate_documents(
        self,
        assessment: Dict[str, Any],
        templates: List[Dict[str, Any]],
        document_types: List[str],
        extracted_data: Dict[str, Any] = None,
        progress_callback: Callable = None,
        clause_ids: List[str] = None,
        language: str = None
    ) -> Dict[str, Any]:
        """
        Full document generation pipeline with retry logic and error handling.

        Args:
            assessment: Assessment data
            templates: Available templates
            document_types: Types of documents to generate
            extracted_data: Data extracted from uploaded documents
            progress_callback: Callback for progress updates
            clause_ids: Optional list of LMA clause IDs to include in documents
            language: Optional target language code
        """
        job_id = str(uuid.uuid4())[:8]
        progress = DocumentGenerationProgress(job_id)
        progress.total_documents = len(document_types)

        results = {
            "job_id": job_id,
            "assessment_id": assessment.get("id"),
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "agent_outputs": {},
            "generated_documents": [],
            "errors": [],
            "progress": []
        }

        try:
            assessment_summary = self._build_assessment_summary(assessment)

            # Pre-populate field mappings from assessment data
            pre_populated_mappings = self._pre_populate_field_mappings(assessment)
            logger.info(f"Pre-populated {pre_populated_mappings['completion_percentage']}% of fields from assessment")

            # Add selected clause IDs to assessment summary for use in document generation
            if clause_ids:
                assessment_summary += f"\n- Selected LMA Clauses: {', '.join(clause_ids)}"
                pre_populated_mappings.setdefault("field_mappings", {})["selected_clauses"] = clause_ids
                logger.info(f"Including {len(clause_ids)} user-selected clauses in document generation")

            # Add target language to assessment summary
            if language:
                assessment_summary += f"\n- Target Language: {language}"
                pre_populated_mappings.setdefault("field_mappings", {})["target_language"] = language
                logger.info(f"Target language for document generation: {language}")

            # =========================================================
            # AGENT 1: Document Requirement Analyzer
            # =========================================================
            progress.start_agent("DocumentRequirementAnalyzer", "Analyzing document requirements...")
            progress.update_progress(5)
            if progress_callback:
                await progress_callback(progress.to_dict())

            requirements = await self._analyze_requirements(assessment_summary, progress)
            progress.complete_agent(json.dumps(requirements)[:200] if requirements else None)
            results["agent_outputs"]["requirements"] = requirements

            # =========================================================
            # AGENT 2: Template Selector
            # =========================================================
            progress.start_agent("TemplateSelector", "Selecting best templates...")
            progress.update_progress(15)
            if progress_callback:
                await progress_callback(progress.to_dict())

            template_selections = await self._select_templates(
                requirements.get("required_documents", []),
                templates,
                progress
            )
            progress.complete_agent(json.dumps(template_selections)[:200] if template_selections else None)
            results["agent_outputs"]["template_selections"] = template_selections

            # =========================================================
            # AGENT 3-5: Process each document
            # =========================================================
            base_progress = 25
            progress_per_doc = 75 // max(len(document_types), 1)

            for idx, doc_type in enumerate(document_types):
                doc_progress = base_progress + (idx * progress_per_doc)
                doc_error = None

                try:
                    # Find template for this document
                    template = self._find_template_for_doc(doc_type, template_selections, templates)
                    if not template:
                        logger.warning(f"No template found for {doc_type}, using fallback")
                        template = {"id": doc_type, "template_key": doc_type, "sections": [], "fields": {}}

                    # =========================================================
                    # AGENT 3: Data Mapper (with pre-populated base)
                    # =========================================================
                    progress.start_agent("DataMapper", f"Mapping data for {doc_type}...")
                    progress.update_progress(doc_progress + 5)
                    if progress_callback:
                        await progress_callback(progress.to_dict())

                    # Start with pre-populated mappings
                    field_mappings = pre_populated_mappings.copy()

                    # Try to enhance with AI mapping
                    try:
                        ai_mappings = await self._map_data(
                            assessment_summary,
                            extracted_data or {},
                            template.get("fields", {}),
                            progress
                        )
                        # Merge AI mappings (but don't override pre-populated values)
                        if ai_mappings and not ai_mappings.get("_error"):
                            for key, val in ai_mappings.get("field_mappings", {}).items():
                                if key not in field_mappings.get("field_mappings", {}):
                                    field_mappings.setdefault("field_mappings", {})[key] = val
                    except Exception as e:
                        logger.warning(f"AI data mapping failed for {doc_type}: {e}")

                    progress.complete_agent(json.dumps(field_mappings)[:200] if field_mappings else None)

                    # =========================================================
                    # AGENT 4: Document Drafter
                    # =========================================================
                    progress.start_agent("DocumentDrafter", f"Drafting {doc_type}...")
                    progress.update_progress(doc_progress + 15)
                    if progress_callback:
                        await progress_callback(progress.to_dict())

                    draft = await self._draft_document(
                        doc_type,
                        template.get("sections", []),
                        field_mappings,
                        assessment_summary,
                        progress
                    )

                    # Check if AI draft failed and use fallback
                    if not draft or draft.get("_error") or not draft.get("sections"):
                        logger.warning(f"AI drafting failed for {doc_type}, using fallback template")
                        draft = self._generate_fallback_document(doc_type, field_mappings, assessment)

                    progress.complete_agent(json.dumps(draft)[:200] if draft else None)

                    # =========================================================
                    # AGENT 5: Compliance Checker
                    # =========================================================
                    progress.start_agent("ComplianceChecker", f"Validating {doc_type}...")
                    progress.update_progress(doc_progress + 20)
                    if progress_callback:
                        await progress_callback(progress.to_dict())

                    compliance = await self._check_compliance(draft, progress)

                    # Provide fallback compliance report if AI fails
                    if not compliance or compliance.get("_error"):
                        total_placeholders = draft.get("total_placeholders", 0)
                        compliance = {
                            "compliance_passed": total_placeholders < 5,
                            "compliance_score": max(0, 100 - (total_placeholders * 5)),
                            "critical_issues": [],
                            "warnings": ["Compliance check performed using fallback rules"],
                            "completeness_check": {
                                "mandatory_fields_present": len(draft.get("sections", [])),
                                "mandatory_fields_missing": total_placeholders,
                                "required_sections_present": len([s for s in draft.get("sections", []) if s.get("is_complete")]),
                                "required_sections_missing": len([s for s in draft.get("sections", []) if not s.get("is_complete")])
                            },
                            "regulatory_notes": [],
                            "approved_for_generation": total_placeholders < 10,
                            "manual_review_required": total_placeholders > 0,
                            "review_reason": f"{total_placeholders} placeholders require completion" if total_placeholders > 0 else ""
                        }

                    progress.complete_agent(json.dumps(compliance)[:200] if compliance else None)

                    # Add selected clauses to draft content
                    if clause_ids:
                        draft["selected_clause_ids"] = clause_ids

                    # Add to results
                    results["generated_documents"].append({
                        "document_type": doc_type,
                        "template_id": template.get("id"),
                        "template_key": template.get("template_key"),
                        "title": draft.get("document_title", f"{doc_type.replace('_', ' ').title()} Document"),
                        "draft_content": draft,
                        "data_mappings": field_mappings,
                        "compliance_report": compliance,
                        "status": "draft" if compliance.get("approved_for_generation") else "review_required",
                        "placeholders_remaining": draft.get("total_placeholders", 0),
                        "ai_confidence": compliance.get("compliance_score", 0) / 100.0,
                        "selected_clause_ids": clause_ids,
                        "language": language,
                        "error": None
                    })

                    progress.completed_documents += 1

                except Exception as e:
                    doc_error = str(e)
                    logger.error(f"Error generating {doc_type}: {e}")
                    progress.add_error(doc_type, doc_error)

                    # Add failed document with error info
                    results["generated_documents"].append({
                        "document_type": doc_type,
                        "template_id": None,
                        "template_key": doc_type,
                        "title": f"{doc_type.replace('_', ' ').title()} Document (Failed)",
                        "draft_content": {},
                        "data_mappings": {},
                        "compliance_report": {
                            "compliance_passed": False,
                            "compliance_score": 0,
                            "critical_issues": [{"issue": doc_error, "severity": "critical"}],
                            "approved_for_generation": False,
                            "manual_review_required": True,
                            "review_reason": f"Generation failed: {doc_error}"
                        },
                        "status": "failed",
                        "placeholders_remaining": 0,
                        "ai_confidence": 0.0,
                        "error": doc_error
                    })

            # Finalize
            progress.update_progress(100)
            results["status"] = "completed" if progress.failed_documents == 0 else "completed_with_errors"
            results["completed_at"] = datetime.now(timezone.utc).isoformat()
            results["errors"] = progress.errors
            results["progress"] = progress.to_dict()

            return results

        except Exception as e:
            logger.error(f"Document generation error: {e}")
            progress.fail_agent(str(e))
            results["status"] = "failed"
            results["error"] = str(e)
            results["errors"] = progress.errors
            results["progress"] = progress.to_dict()
            return results

    def _build_assessment_summary(self, assessment: Dict[str, Any]) -> str:
        """Build assessment summary for agents."""
        return f"""
ASSESSMENT DETAILS:
- Reference: {assessment.get('reference_number', 'N/A')}
- Title: {assessment.get('title', 'N/A')}
- Risk Category: {assessment.get('risk_category', 'N/A')}
- Decision: {assessment.get('decision', 'PENDING')}
- Insured: {assessment.get('insured_name', 'N/A')}
- Insured Entity: {assessment.get('insured_entity_name', 'N/A')}
- Companies House: {assessment.get('companies_house_number', 'N/A')}
- Broker: {assessment.get('broker_name', 'N/A')}
- Broker Reference: {assessment.get('broker_reference', 'N/A')}
- Commission: {assessment.get('commission_rate', 'N/A')}%
- Premium: {assessment.get('premium', 'N/A')}
- Sum Insured: {assessment.get('sum_insured', 'N/A')}
- Deductible: {assessment.get('deductible', 'N/A')}
- Territory: {assessment.get('territory', 'N/A')}
- Inception Date: {assessment.get('inception_date', 'N/A')}
- Expiry Date: {assessment.get('expiry_date', 'N/A')}
- Renewal Date: {assessment.get('renewal_date', 'N/A')}
- Risk Score: {assessment.get('risk_score', 'N/A')}
- Regulatory Framework: {assessment.get('regulatory_framework', 'N/A')}
- Loss Run Rules: {assessment.get('loss_run_reporting_rules', 'N/A')}
"""

    async def _analyze_requirements(self, assessment_summary: str, progress: DocumentGenerationProgress = None) -> Dict:
        """Agent 1: Analyze document requirements with retry."""
        messages = [
            {"role": "system", "content": REQUIREMENT_ANALYZER_PROMPT},
            {"role": "user", "content": f"Analyze requirements for:\n\n{assessment_summary}"}
        ]

        try:
            response = await self._call_llm_with_retry(messages, temperature=0.1, progress=progress)
            return self._parse_json_with_retry(response, "requirement_analysis")
        except Exception as e:
            logger.error(f"Requirement analysis failed: {e}")
            # Return sensible defaults
            return {
                "required_documents": [
                    {"document_type": "lloyds_mrc_slip", "priority": 1, "mandatory": True, "confidence": 0.95, "reason": "Standard Lloyd's slip"},
                    {"document_type": "certificate_of_insurance", "priority": 2, "mandatory": True, "confidence": 0.90, "reason": "Proof of coverage"}
                ],
                "bundle_name": "Standard Document Bundle",
                "total_documents": 2,
                "special_considerations": ["Default requirements used due to analysis failure"]
            }

    async def _select_templates(self, requirements: List[Dict], templates: List[Dict], progress: DocumentGenerationProgress = None) -> Dict:
        """Agent 2: Select templates for requirements with retry."""
        template_summary = json.dumps([
            {"id": t.get("id"), "key": t.get("template_key"), "name": t.get("name"),
             "category": t.get("category"), "document_type": t.get("document_type")}
            for t in templates
        ], indent=2)

        prompt = TEMPLATE_SELECTOR_PROMPT.replace("{templates}", template_summary)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Select templates for:\n\n{json.dumps(requirements, indent=2)}"}
        ]

        try:
            response = await self._call_llm_with_retry(messages, temperature=0.1, progress=progress)
            return self._parse_json_with_retry(response, "template_selection")
        except Exception as e:
            logger.error(f"Template selection failed: {e}")
            return {"template_selections": [], "all_templates_matched": False}

    async def _map_data(
        self,
        assessment_summary: str,
        document_data: Dict,
        template_fields: Dict,
        progress: DocumentGenerationProgress = None
    ) -> Dict:
        """Agent 3: Map data to template fields with retry."""
        prompt = DATA_MAPPER_PROMPT.replace(
            "{assessment_data}", assessment_summary
        ).replace(
            "{document_data}", json.dumps(document_data, default=str)[:2000]
        ).replace(
            "{template_fields}", json.dumps(template_fields, default=str)[:2000]
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Map the data to template fields."}
        ]

        try:
            response = await self._call_llm_with_retry(messages, temperature=0.1, progress=progress)
            return self._parse_json_with_retry(response, "data_mapping")
        except Exception as e:
            logger.error(f"Data mapping failed: {e}")
            return {"field_mappings": {}, "unmapped_fields": [], "completion_percentage": 0,
                   "notes": f"AI mapping failed: {e}"}

    async def _draft_document(
        self,
        document_type: str,
        template_sections: List[Dict],
        field_mappings: Dict,
        assessment_summary: str,
        progress: DocumentGenerationProgress = None
    ) -> Dict:
        """Agent 4: Draft document content with retry."""
        # Use standard sections if template has none
        if not template_sections:
            template_sections = LLOYDS_DOCUMENT_SECTIONS.get(document_type, [])

        prompt = DOCUMENT_DRAFTER_PROMPT.replace(
            "{document_type}", document_type
        ).replace(
            "{template_sections}", json.dumps(template_sections, default=str)[:2000]
        ).replace(
            "{field_mappings}", json.dumps(field_mappings, default=str)[:2000]
        ).replace(
            "{assessment_summary}", assessment_summary
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate the complete document content with all sections fully populated."}
        ]

        try:
            response = await self._call_llm_with_retry(messages, temperature=0.2, max_tokens=16000, progress=progress)
            result = self._parse_json_with_retry(response, f"document_draft_{document_type}")

            # Validate result has required structure
            if result and result.get("sections") and len(result["sections"]) > 0:
                return result
            else:
                logger.warning(f"AI draft for {document_type} has no sections, will use fallback")
                return {"_error": "No sections generated"}

        except Exception as e:
            logger.error(f"Document drafting failed for {document_type}: {e}")
            return {"_error": str(e)}

    async def _check_compliance(self, draft_document: Dict, progress: DocumentGenerationProgress = None) -> Dict:
        """Agent 5: Check compliance with retry."""
        prompt = COMPLIANCE_CHECKER_PROMPT.replace(
            "{draft_document}", json.dumps(draft_document, default=str)[:3000]
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Validate compliance of the generated document."}
        ]

        try:
            response = await self._call_llm_with_retry(messages, temperature=0.1, progress=progress)
            return self._parse_json_with_retry(response, "compliance_check")
        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
            return {"_error": str(e)}

    def _find_template_for_doc(
        self,
        doc_type: str,
        selections: Dict,
        templates: List[Dict]
    ) -> Optional[Dict]:
        """Find the template for a document type."""
        # Check selections first
        for sel in selections.get("template_selections", []):
            if sel.get("document_type") == doc_type:
                template_id = sel.get("template_id")
                for t in templates:
                    if t.get("id") == template_id:
                        return t

        # Fallback: match by document_type, template_key, or id
        for t in templates:
            if t.get("document_type") == doc_type or t.get("template_key") == doc_type or t.get("id") == doc_type:
                return t

        return None

    async def prefill_template(
        self,
        assessment: Dict[str, Any],
        template: Dict[str, Any],
        extracted_data: Dict[str, Any] = None,
        rag_context: str = None
    ) -> Dict[str, Any]:
        """
        Get AI-prefilled data for a single template.
        """
        # Start with pre-populated mappings
        field_mappings = self._pre_populate_field_mappings(assessment)

        # Combine extracted data with RAG context if available
        combined_data = extracted_data or {}
        if rag_context:
            combined_data["_rag_context"] = rag_context

        # Try to enhance with AI mapping
        assessment_summary = self._build_assessment_summary(assessment)
        try:
            ai_mappings = await self._map_data(
                assessment_summary,
                combined_data,
                template.get("fields", {})
            )
            if ai_mappings and not ai_mappings.get("_error"):
                for key, val in ai_mappings.get("field_mappings", {}).items():
                    if key not in field_mappings.get("field_mappings", {}):
                        field_mappings.setdefault("field_mappings", {})[key] = val
        except Exception as e:
            logger.warning(f"AI data mapping enhancement failed: {e}")

        unmapped = [k for k, v in field_mappings.get("field_mappings", {}).items()
                    if v.get("source") == "manual_required" or v.get("value") is None]

        return {
            "template_id": template.get("id"),
            "template_name": template.get("name"),
            "field_mappings": field_mappings.get("field_mappings", {}),
            "unmapped_fields": unmapped,
            "data_conflicts": field_mappings.get("data_conflicts", []),
            "completion_percentage": field_mappings.get("completion_percentage", 0),
            "rag_context_used": rag_context is not None
        }


# Singleton instance
document_generator = DocumentGenerationPipeline()
