"""
InstantRisk V3 - Intelligent Document Generator

Automatically generates complete insurance documents with:
1. Auto-selection of templates based on risk analysis
2. Auto-population of all fields from extracted data
3. Intelligent clause selection based on risk profile
4. Automatic customization of terms and conditions
5. Complete document generation ready for human approval

This ELIMINATES underwriter document work - just human supervision.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class DocumentPurpose(str, Enum):
    """Purpose of generated document."""
    QUOTE = "quote"
    SLIP = "slip"
    BINDER = "binder"
    POLICY = "policy"
    CERTIFICATE = "certificate"
    ENDORSEMENT = "endorsement"
    RENEWAL = "renewal"
    CLAIMS_ADVICE = "claims_advice"


@dataclass
class ClauseSelection:
    """Selected clause with reasoning."""
    clause_id: str
    clause_reference: str  # e.g., LMA1234, LSW567
    clause_title: str
    clause_text: str
    selection_reason: str
    is_mandatory: bool
    applies_to_risk: bool
    confidence: float


@dataclass
class TemplateSelection:
    """Selected template with field mappings."""
    template_id: str
    template_name: str
    purpose: DocumentPurpose
    selection_reason: str
    field_mappings: Dict[str, Any]
    completeness_score: float
    missing_fields: List[str]


@dataclass
class GeneratedDocument:
    """Complete generated document."""
    document_id: str
    template_used: str
    purpose: DocumentPurpose
    title: str
    sections: List[Dict[str, Any]]
    clauses_attached: List[ClauseSelection]
    completeness_score: float
    missing_data: List[str]
    ready_for_review: bool
    generation_notes: List[str]
    requires_human_input: List[Dict[str, str]]


class IntelligentDocumentGenerator:
    """
    Generates complete insurance documents automatically.

    Features:
    - Auto-selects appropriate templates
    - Auto-maps extracted data to fields
    - Auto-selects clauses based on risk profile
    - Generates complete documents ready for approval
    """

    # Template selection rules based on risk type and coverage
    TEMPLATE_SELECTION_RULES = {
        # Marine risks
        "marine": {
            "primary": ["lloyds_mrc_slip", "marine_cargo", "marine_hull"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["LMA1234", "LMA5402", "CL382", "CL385", "CL386"],
        },
        "cargo": {
            "primary": ["marine_cargo"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["LMA1234", "CL382", "INCOTERMS"],
        },
        "hull": {
            "primary": ["marine_hull"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["ITCH83", "LMA1234", "LMA5403"],
        },
        # Property risks
        "property": {
            "primary": ["commercial_property", "lloyds_mrc_slip"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["LMA5217", "LMA5218", "LSW555", "NMA2918"],
        },
        "fire": {
            "primary": ["commercial_property"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["LMA5217", "NMA2918"],
        },
        # Liability risks
        "liability": {
            "primary": ["commercial_general_liability", "lloyds_mrc_slip"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["LMA5218", "LSW555"],
        },
        "professional_indemnity": {
            "primary": ["professional_indemnity", "lloyds_mrc_slip"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["LMA5239", "LSW1290"],
        },
        # Specialty risks
        "cyber": {
            "primary": ["cyber_liability"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["LMA5400", "LMA5401", "CL380"],
        },
        "d&o": {
            "primary": ["directors_officers"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["LSW1563", "LSW1564"],
        },
        "aviation": {
            "primary": ["aviation", "lloyds_mrc_slip"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["AVN48B", "AVN52", "AVN67B"],
        },
        "energy": {
            "primary": ["energy", "lloyds_mrc_slip"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["LSW620", "WELCAR"],
        },
        "construction": {
            "primary": ["construction", "lloyds_mrc_slip"],
            "secondary": ["certificate_of_insurance"],
            "clauses": ["MUNICHRE", "LEG3"],
        },
        "political_risk": {
            "primary": ["political_risk"],
            "secondary": [],
            "clauses": ["LMA3100", "LMA3102"],
        },
        # Reinsurance
        "reinsurance": {
            "primary": ["treaty_slip", "facultative_certificate"],
            "secondary": [],
            "clauses": ["LMA5093", "LMA5096"],
        },
    }

    # Standard clause library
    STANDARD_CLAUSES = {
        # General Clauses
        "LMA5217": {
            "reference": "LMA5217",
            "title": "Communicable Disease Exclusion",
            "category": "exclusion",
            "applies_to": ["property", "liability", "marine"],
            "mandatory_for": [],
            "text_summary": "Excludes losses directly or indirectly caused by communicable diseases"
        },
        "LMA5218": {
            "reference": "LMA5218",
            "title": "Cyber War and Cyber Operation Exclusion",
            "category": "exclusion",
            "applies_to": ["property", "liability", "marine"],
            "mandatory_for": [],
            "text_summary": "Excludes cyber operations that constitute war or retaliatory attacks"
        },
        "LMA5400": {
            "reference": "LMA5400",
            "title": "Cyber Attack Exclusion",
            "category": "exclusion",
            "applies_to": ["property", "marine"],
            "mandatory_for": ["property"],
            "text_summary": "Excludes losses from cyber attacks on non-cyber policies"
        },
        "LMA5401": {
            "reference": "LMA5401",
            "title": "Cyber Losses Write-Back",
            "category": "extension",
            "applies_to": ["cyber"],
            "mandatory_for": [],
            "text_summary": "Writes back covered cyber losses on cyber policies"
        },
        # Marine Clauses
        "CL382": {
            "reference": "CL382",
            "title": "Institute War Clauses (Cargo)",
            "category": "cover",
            "applies_to": ["marine", "cargo"],
            "mandatory_for": ["cargo"],
            "text_summary": "Standard war risk cover for cargo shipments"
        },
        "CL385": {
            "reference": "CL385",
            "title": "Institute Cargo Clauses (A)",
            "category": "cover",
            "applies_to": ["cargo"],
            "mandatory_for": ["cargo"],
            "text_summary": "All risks cargo cover"
        },
        "CL386": {
            "reference": "CL386",
            "title": "Institute Cargo Clauses (B)",
            "category": "cover",
            "applies_to": ["cargo"],
            "mandatory_for": [],
            "text_summary": "Named perils cargo cover"
        },
        # Sanctions Clauses
        "LMA3100": {
            "reference": "LMA3100",
            "title": "Sanctions Limitation and Exclusion Clause",
            "category": "exclusion",
            "applies_to": ["all"],
            "mandatory_for": ["all"],
            "text_summary": "Excludes cover where it would violate sanctions"
        },
        # War and Terrorism
        "NMA2918": {
            "reference": "NMA2918",
            "title": "War and Civil War Exclusion Clause",
            "category": "exclusion",
            "applies_to": ["property", "liability"],
            "mandatory_for": ["property"],
            "text_summary": "Excludes war, civil war, rebellion, and similar events"
        },
        "LSW555": {
            "reference": "LSW555",
            "title": "Terrorism Exclusion Endorsement",
            "category": "exclusion",
            "applies_to": ["property", "liability"],
            "mandatory_for": ["property"],
            "text_summary": "Excludes losses from acts of terrorism"
        },
        # Nuclear
        "NMA1975": {
            "reference": "NMA1975",
            "title": "Nuclear Incident Exclusion Clause",
            "category": "exclusion",
            "applies_to": ["all"],
            "mandatory_for": ["property", "liability"],
            "text_summary": "Excludes nuclear and radioactive contamination"
        },
        # Asbestos
        "NMA2983": {
            "reference": "NMA2983",
            "title": "Asbestos Exclusion",
            "category": "exclusion",
            "applies_to": ["liability", "property"],
            "mandatory_for": ["liability"],
            "text_summary": "Excludes asbestos-related losses"
        },
    }

    # Mandatory clauses by risk type
    MANDATORY_CLAUSES = {
        "all": ["LMA3100"],  # Sanctions always required
        "property": ["NMA2918", "NMA1975", "LMA5400"],
        "liability": ["NMA1975", "NMA2983"],
        "marine": ["CL382"],
        "cargo": ["CL385", "CL382"],
        "cyber": ["LMA5401"],
    }

    def __init__(self):
        pass

    def select_templates(
        self,
        extraction_data: Dict[str, Any],
        risk_analysis: Dict[str, Any],
        underwriting_decision: Dict[str, Any]
    ) -> List[TemplateSelection]:
        """
        Automatically select appropriate templates based on analysis.

        Args:
            extraction_data: Extracted document data
            risk_analysis: Risk analysis results
            underwriting_decision: Underwriting decision

        Returns:
            List of selected templates with mappings
        """
        selected = []

        # Determine risk type
        coverage = extraction_data.get("coverage", {})
        risk_type = coverage.get("type", "").lower()
        class_of_business = coverage.get("class_of_business", "").lower()

        # Find matching template rules
        matching_rules = self._find_matching_rules(risk_type, class_of_business)

        if not matching_rules:
            # Default to general Lloyd's slip
            matching_rules = {
                "primary": ["lloyds_mrc_slip"],
                "secondary": ["certificate_of_insurance"],
                "clauses": []
            }

        # Create template selections
        for template_id in matching_rules.get("primary", []):
            field_mappings, missing = self._map_fields_to_template(
                template_id, extraction_data
            )
            completeness = 1.0 - (len(missing) / max(len(field_mappings) + len(missing), 1))

            selected.append(TemplateSelection(
                template_id=template_id,
                template_name=template_id.replace("_", " ").title(),
                purpose=DocumentPurpose.SLIP,
                selection_reason=f"Primary template for {risk_type} risk",
                field_mappings=field_mappings,
                completeness_score=completeness,
                missing_fields=missing
            ))

        # Add secondary templates
        for template_id in matching_rules.get("secondary", []):
            field_mappings, missing = self._map_fields_to_template(
                template_id, extraction_data
            )
            completeness = 1.0 - (len(missing) / max(len(field_mappings) + len(missing), 1))

            selected.append(TemplateSelection(
                template_id=template_id,
                template_name=template_id.replace("_", " ").title(),
                purpose=DocumentPurpose.CERTIFICATE,
                selection_reason=f"Supporting document for {risk_type} risk",
                field_mappings=field_mappings,
                completeness_score=completeness,
                missing_fields=missing
            ))

        return selected

    def select_clauses(
        self,
        extraction_data: Dict[str, Any],
        risk_analysis: Dict[str, Any],
        underwriting_decision: Dict[str, Any]
    ) -> List[ClauseSelection]:
        """
        Automatically select appropriate clauses based on risk profile.

        Args:
            extraction_data: Extracted document data
            risk_analysis: Risk analysis results
            underwriting_decision: Underwriting decision

        Returns:
            List of selected clauses
        """
        selected_clauses = []

        # Determine risk type
        coverage = extraction_data.get("coverage", {})
        risk_type = coverage.get("type", "").lower()

        # Get exposure analysis
        exposures = risk_analysis.get("exposure_analysis", {}) if risk_analysis else {}

        # 1. Add mandatory clauses for all risks
        for clause_id in self.MANDATORY_CLAUSES.get("all", []):
            if clause_id in self.STANDARD_CLAUSES:
                clause = self.STANDARD_CLAUSES[clause_id]
                selected_clauses.append(ClauseSelection(
                    clause_id=clause_id,
                    clause_reference=clause["reference"],
                    clause_title=clause["title"],
                    clause_text=clause["text_summary"],
                    selection_reason="Mandatory for all Lloyd's risks",
                    is_mandatory=True,
                    applies_to_risk=True,
                    confidence=1.0
                ))

        # 2. Add risk-type specific mandatory clauses
        for clause_id in self.MANDATORY_CLAUSES.get(risk_type, []):
            if clause_id in self.STANDARD_CLAUSES and clause_id not in [c.clause_id for c in selected_clauses]:
                clause = self.STANDARD_CLAUSES[clause_id]
                selected_clauses.append(ClauseSelection(
                    clause_id=clause_id,
                    clause_reference=clause["reference"],
                    clause_title=clause["title"],
                    clause_text=clause["text_summary"],
                    selection_reason=f"Mandatory for {risk_type} risks",
                    is_mandatory=True,
                    applies_to_risk=True,
                    confidence=1.0
                ))

        # 3. Add exposure-based clauses
        self._add_exposure_based_clauses(selected_clauses, exposures, risk_type)

        # 4. Add underwriting-recommended clauses
        if underwriting_decision:
            terms = underwriting_decision.get("terms_assessment", {})
            for condition in terms.get("conditions_to_add", []):
                if isinstance(condition, dict):
                    selected_clauses.append(ClauseSelection(
                        clause_id=f"UW_{len(selected_clauses)}",
                        clause_reference="Custom",
                        clause_title=condition.get("condition", "Custom Condition")[:50],
                        clause_text=condition.get("condition", ""),
                        selection_reason=condition.get("reason", "Underwriter recommendation"),
                        is_mandatory=True,
                        applies_to_risk=True,
                        confidence=0.9
                    ))

        return selected_clauses

    def generate_document(
        self,
        template_selection: TemplateSelection,
        clauses: List[ClauseSelection],
        extraction_data: Dict[str, Any],
        underwriting_decision: Dict[str, Any]
    ) -> GeneratedDocument:
        """
        Generate a complete document from template and data.

        Args:
            template_selection: Selected template
            clauses: Selected clauses
            extraction_data: Extracted data
            underwriting_decision: Underwriting decision

        Returns:
            Complete generated document
        """
        sections = []
        generation_notes = []
        requires_human_input = []

        # Generate sections based on template type
        if "slip" in template_selection.template_id.lower() or "mrc" in template_selection.template_id.lower():
            sections = self._generate_slip_sections(
                extraction_data,
                underwriting_decision,
                template_selection,
                generation_notes,
                requires_human_input
            )
        elif "certificate" in template_selection.template_id.lower():
            sections = self._generate_certificate_sections(
                extraction_data,
                template_selection,
                generation_notes,
                requires_human_input
            )
        elif "policy" in template_selection.template_id.lower():
            sections = self._generate_policy_sections(
                extraction_data,
                underwriting_decision,
                clauses,
                generation_notes,
                requires_human_input
            )

        # Calculate completeness
        total_fields = sum(len(section.get("fields", {})) for section in sections)
        filled_fields = sum(
            1 for section in sections
            for field in section.get("fields", {}).values()
            if field is not None and field != ""
        )
        completeness = filled_fields / max(total_fields, 1)

        # Collect missing data
        missing_data = template_selection.missing_fields.copy()
        for section in sections:
            for field_name, value in section.get("fields", {}).items():
                if value is None or value == "":
                    if field_name not in missing_data:
                        missing_data.append(field_name)

        doc_id = f"GEN_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return GeneratedDocument(
            document_id=doc_id,
            template_used=template_selection.template_id,
            purpose=template_selection.purpose,
            title=self._generate_document_title(extraction_data, template_selection),
            sections=sections,
            clauses_attached=clauses,
            completeness_score=completeness,
            missing_data=missing_data,
            ready_for_review=completeness >= 0.8 and len(requires_human_input) <= 3,
            generation_notes=generation_notes,
            requires_human_input=requires_human_input
        )

    def _find_matching_rules(self, risk_type: str, class_of_business: str) -> Dict:
        """Find matching template selection rules."""
        # Try exact match first
        if risk_type in self.TEMPLATE_SELECTION_RULES:
            return self.TEMPLATE_SELECTION_RULES[risk_type]

        # Try class of business
        if class_of_business in self.TEMPLATE_SELECTION_RULES:
            return self.TEMPLATE_SELECTION_RULES[class_of_business]

        # Try partial match
        for key, rules in self.TEMPLATE_SELECTION_RULES.items():
            if key in risk_type or risk_type in key:
                return rules
            if key in class_of_business or class_of_business in key:
                return rules

        return None

    def _map_fields_to_template(
        self,
        template_id: str,
        extraction_data: Dict
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Map extracted data to template fields."""
        mappings = {}
        missing = []

        # Standard field mappings
        field_map = {
            # Insured
            "insured_name": ["insured", "name"],
            "insured_address": ["insured", "address"],
            "insured_country": ["insured", "country"],

            # Broker
            "broker_name": ["broker", "name"],
            "broker_reference": ["broker", "reference"],

            # Coverage
            "coverage_type": ["coverage", "type"],
            "class_of_business": ["coverage", "class_of_business"],
            "territorial_scope": ["coverage", "territorial_scope"],
            "basis_of_cover": ["coverage", "basis_of_cover"],

            # Financials
            "sum_insured": ["financials", "sum_insured"],
            "limit_of_liability": ["financials", "limit_of_liability"],
            "premium": ["financials", "premium"],
            "deductible": ["financials", "deductible"],
            "currency": ["financials", "currency"],

            # Period
            "inception_date": ["period", "inception_date"],
            "expiry_date": ["period", "expiry_date"],

            # Identifiers
            "umr": ["identifiers", "unique_market_reference"],
            "policy_number": ["identifiers", "policy_number"],
        }

        for field_name, path in field_map.items():
            value = extraction_data
            try:
                for key in path:
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        value = None
                        break

                if value is not None and value != "":
                    mappings[field_name] = value
                else:
                    missing.append(field_name)
            except:
                missing.append(field_name)

        return mappings, missing

    def _add_exposure_based_clauses(
        self,
        selected_clauses: List[ClauseSelection],
        exposures: Dict,
        risk_type: str
    ):
        """Add clauses based on identified exposures."""
        existing_ids = {c.clause_id for c in selected_clauses}

        # Cyber exposure
        cyber_exp = exposures.get("cyber", {})
        if cyber_exp.get("silent_cyber") or cyber_exp.get("exposed"):
            if "LMA5400" not in existing_ids:
                clause = self.STANDARD_CLAUSES.get("LMA5400", {})
                if clause:
                    selected_clauses.append(ClauseSelection(
                        clause_id="LMA5400",
                        clause_reference=clause["reference"],
                        clause_title=clause["title"],
                        clause_text=clause["text_summary"],
                        selection_reason="Silent cyber exposure identified",
                        is_mandatory=False,
                        applies_to_risk=True,
                        confidence=0.95
                    ))

        # Terrorism exposure
        terrorism_exp = exposures.get("terrorism", {})
        if terrorism_exp.get("exposed"):
            if "LSW555" not in existing_ids:
                clause = self.STANDARD_CLAUSES.get("LSW555", {})
                if clause:
                    selected_clauses.append(ClauseSelection(
                        clause_id="LSW555",
                        clause_reference=clause["reference"],
                        clause_title=clause["title"],
                        clause_text=clause["text_summary"],
                        selection_reason="Terrorism exposure identified",
                        is_mandatory=False,
                        applies_to_risk=True,
                        confidence=0.9
                    ))

        # Pandemic exposure
        pandemic_exp = exposures.get("pandemic", {})
        if pandemic_exp.get("exposed"):
            if "LMA5217" not in existing_ids:
                clause = self.STANDARD_CLAUSES.get("LMA5217", {})
                if clause:
                    selected_clauses.append(ClauseSelection(
                        clause_id="LMA5217",
                        clause_reference=clause["reference"],
                        clause_title=clause["title"],
                        clause_text=clause["text_summary"],
                        selection_reason="Communicable disease exposure",
                        is_mandatory=True,
                        applies_to_risk=True,
                        confidence=0.95
                    ))

    def _generate_slip_sections(
        self,
        extraction_data: Dict,
        underwriting_decision: Dict,
        template_selection: TemplateSelection,
        notes: List[str],
        requires_human: List[Dict]
    ) -> List[Dict]:
        """Generate MRC/Slip sections."""
        sections = []
        mappings = template_selection.field_mappings

        # Section 1: Risk Details
        insured = extraction_data.get("insured", {})
        sections.append({
            "section_id": "risk_details",
            "title": "RISK DETAILS",
            "order": 1,
            "fields": {
                "unique_market_reference": mappings.get("umr") or "[UMR TO BE ASSIGNED]",
                "type_of_insurance": mappings.get("coverage_type"),
                "insured": insured.get("name") or "[INSURED NAME REQUIRED]",
                "address": insured.get("address"),
                "business_description": insured.get("industry"),
            }
        })

        # Check if insured name missing
        if not insured.get("name"):
            requires_human.append({
                "field": "insured_name",
                "section": "Risk Details",
                "reason": "Insured name not extracted from document"
            })

        # Section 2: Period
        period = extraction_data.get("period", {})
        sections.append({
            "section_id": "period",
            "title": "PERIOD",
            "order": 2,
            "fields": {
                "inception": period.get("inception_date") or "[DATE REQUIRED]",
                "expiry": period.get("expiry_date") or "[DATE REQUIRED]",
                "period_text": period.get("period_text"),
            }
        })

        # Section 3: Interest
        coverage = extraction_data.get("coverage", {})
        sections.append({
            "section_id": "interest",
            "title": "INTEREST",
            "order": 3,
            "fields": {
                "interest_description": coverage.get("type"),
                "territorial_scope": coverage.get("territorial_scope"),
                "basis_of_valuation": coverage.get("basis_of_cover"),
            }
        })

        # Section 4: Limits and Sums Insured
        financials = extraction_data.get("financials", {})
        sections.append({
            "section_id": "limits",
            "title": "LIMITS OF LIABILITY / SUMS INSURED",
            "order": 4,
            "fields": {
                "sum_insured": financials.get("sum_insured_text") or financials.get("sum_insured"),
                "limit_of_liability": financials.get("limit_text") or financials.get("limit_of_liability"),
                "sublimits": financials.get("sublimits"),
                "currency": financials.get("currency", "GBP"),
            }
        })

        # Section 5: Premium
        sections.append({
            "section_id": "premium",
            "title": "PREMIUM",
            "order": 5,
            "fields": {
                "premium": financials.get("premium_text") or financials.get("premium"),
                "payment_terms": financials.get("premium_payment_terms"),
                "deposit_premium": financials.get("deposit_premium"),
                "minimum_premium": financials.get("minimum_premium"),
                "adjustable": financials.get("adjustable"),
            }
        })

        # Section 6: Deductible
        sections.append({
            "section_id": "deductible",
            "title": "DEDUCTIBLE / EXCESS",
            "order": 6,
            "fields": {
                "deductible": financials.get("deductible_text") or financials.get("deductible"),
                "excess": financials.get("excess"),
            }
        })

        # Section 7: Conditions (from underwriting)
        conditions = extraction_data.get("conditions", {})
        uw_conditions = []
        if underwriting_decision:
            terms = underwriting_decision.get("terms_assessment", {})
            uw_conditions = terms.get("conditions_to_add", [])

        sections.append({
            "section_id": "conditions",
            "title": "CONDITIONS",
            "order": 7,
            "fields": {
                "warranties": conditions.get("warranties", []),
                "subjectivities": conditions.get("subjectivities", []),
                "special_conditions": conditions.get("special_conditions", []),
                "underwriter_conditions": uw_conditions,
            }
        })

        # Section 8: Security
        syndicate = extraction_data.get("syndicate_info", {})
        sections.append({
            "section_id": "security",
            "title": "SECURITY",
            "order": 8,
            "fields": {
                "lead_underwriter": syndicate.get("lead_underwriter"),
                "syndicates": syndicate.get("participating_syndicates", []),
                "signed_line": syndicate.get("total_signed_line"),
            }
        })

        # Section 9: Broker
        broker = extraction_data.get("broker", {})
        sections.append({
            "section_id": "broker",
            "title": "BROKER",
            "order": 9,
            "fields": {
                "broker_name": broker.get("name"),
                "broker_reference": broker.get("reference"),
                "contact": broker.get("contact_name"),
            }
        })

        notes.append(f"Generated {len(sections)} sections from extracted data")
        return sections

    def _generate_certificate_sections(
        self,
        extraction_data: Dict,
        template_selection: TemplateSelection,
        notes: List[str],
        requires_human: List[Dict]
    ) -> List[Dict]:
        """Generate certificate of insurance sections."""
        sections = []

        insured = extraction_data.get("insured", {})
        period = extraction_data.get("period", {})
        financials = extraction_data.get("financials", {})
        coverage = extraction_data.get("coverage", {})
        broker = extraction_data.get("broker", {})

        sections.append({
            "section_id": "certificate_details",
            "title": "CERTIFICATE OF INSURANCE",
            "order": 1,
            "fields": {
                "certificate_number": "[AUTO-GENERATED]",
                "insured_name": insured.get("name"),
                "insured_address": insured.get("address"),
                "coverage_type": coverage.get("type"),
                "policy_number": extraction_data.get("identifiers", {}).get("policy_number"),
                "inception_date": period.get("inception_date"),
                "expiry_date": period.get("expiry_date"),
                "sum_insured": financials.get("sum_insured"),
                "premium": financials.get("premium"),
                "broker": broker.get("name"),
            }
        })

        notes.append("Generated certificate from extracted data")
        return sections

    def _generate_policy_sections(
        self,
        extraction_data: Dict,
        underwriting_decision: Dict,
        clauses: List[ClauseSelection],
        notes: List[str],
        requires_human: List[Dict]
    ) -> List[Dict]:
        """Generate policy wording sections."""
        # Similar structure to slip but with full policy wording
        sections = self._generate_slip_sections(
            extraction_data,
            underwriting_decision,
            TemplateSelection(
                template_id="policy",
                template_name="Policy",
                purpose=DocumentPurpose.POLICY,
                selection_reason="",
                field_mappings={},
                completeness_score=0,
                missing_fields=[]
            ),
            notes,
            requires_human
        )

        # Add clauses section
        clause_section = {
            "section_id": "clauses",
            "title": "CLAUSES AND CONDITIONS",
            "order": 10,
            "fields": {
                "attached_clauses": [
                    {
                        "reference": c.clause_reference,
                        "title": c.clause_title,
                        "mandatory": c.is_mandatory
                    }
                    for c in clauses
                ]
            }
        }
        sections.append(clause_section)

        return sections

    def _generate_document_title(
        self,
        extraction_data: Dict,
        template_selection: TemplateSelection
    ) -> str:
        """Generate document title."""
        insured = extraction_data.get("insured", {}).get("name", "Unknown")
        coverage = extraction_data.get("coverage", {}).get("type", "Insurance")
        purpose = template_selection.purpose.value.title()

        return f"{insured} - {coverage} {purpose}"


# Singleton instance
intelligent_generator = IntelligentDocumentGenerator()
