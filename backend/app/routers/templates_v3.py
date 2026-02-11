"""
Templates V3 Router - Enhanced Insurance Document Templates API

Provides access to policy templates, clauses, and forms organized by
line of business with filtering and search capabilities.

Key features:
- Policy templates by line of business
- Clause templates by type and line
- Form templates
- Lines of business listing
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()

# Base path for templates
TEMPLATES_BASE_PATH = Path("/app/data/templates")
POLICIES_PATH = TEMPLATES_BASE_PATH / "policies"
CLAUSES_PATH = TEMPLATES_BASE_PATH / "clauses"
FORMS_PATH = TEMPLATES_BASE_PATH / "forms"


# =============================================================================
# Response Schemas
# =============================================================================

class PolicyTemplateBase(BaseModel):
    """Basic policy template information."""
    id: str
    name: str
    category: str
    line_of_business: str
    description: str
    insurer: Optional[str] = None
    form_number: Optional[str] = None
    tags: List[str] = []


class PolicyTemplateDetail(PolicyTemplateBase):
    """Detailed policy template with sections and variables."""
    sections: List[Dict[str, Any]] = []
    variables: List[str] = []
    source: Optional[str] = None
    effective_date: Optional[str] = None


class PolicyTemplatesResponse(BaseModel):
    """Response for listing policy templates."""
    count: int
    line_of_business: Optional[str] = None
    templates: List[PolicyTemplateBase]


class ClauseBase(BaseModel):
    """Basic clause information."""
    id: str
    name: str
    typical_use: Optional[str] = None
    line_of_business: str


class ClauseDetail(ClauseBase):
    """Detailed clause with full text."""
    text: str
    source: Optional[str] = None


class ClauseTypeResponse(BaseModel):
    """Response for clause type collection."""
    id: str
    name: str
    type: str
    description: str
    total_clauses: int
    clauses: List[ClauseDetail]
    tags: List[str] = []


class ClausesResponse(BaseModel):
    """Response for listing clauses."""
    count: int
    clause_type: Optional[str] = None
    line_of_business: Optional[str] = None
    clauses: List[ClauseDetail]


class FormTemplate(BaseModel):
    """Form template information."""
    id: str
    name: str
    form_type: str
    description: str
    fields: List[Dict[str, Any]] = []


class FormTemplateResponse(BaseModel):
    """Response for form template."""
    form: FormTemplate


class LineOfBusiness(BaseModel):
    """Line of business information."""
    id: str
    name: str
    display_name: str
    description: str
    policy_count: int
    clause_types: List[str] = []


class LinesOfBusinessResponse(BaseModel):
    """Response for lines of business listing."""
    count: int
    lines: List[LineOfBusiness]


# =============================================================================
# Helper Functions
# =============================================================================

def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """Load and parse a JSON file."""
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading {path}: {e}")
    return None


def _load_policies_for_line(line: str) -> List[Dict[str, Any]]:
    """Load all policy templates for a specific line of business."""
    policies = []
    line_path = POLICIES_PATH / line

    if line_path.exists() and line_path.is_dir():
        for json_file in line_path.glob("*.json"):
            policy = _load_json_file(json_file)
            if policy:
                policies.append(policy)

    return policies


def _load_all_policies() -> List[Dict[str, Any]]:
    """Load all policy templates from all lines of business."""
    all_policies = []

    if POLICIES_PATH.exists():
        for line_dir in POLICIES_PATH.iterdir():
            if line_dir.is_dir():
                all_policies.extend(_load_policies_for_line(line_dir.name))

    return all_policies


def _load_clauses_by_type(clause_type: str) -> Optional[Dict[str, Any]]:
    """Load clauses by type."""
    type_path = CLAUSES_PATH / "by_type" / f"{clause_type}.json"
    return _load_json_file(type_path)


def _load_all_clause_types() -> List[Dict[str, Any]]:
    """Load all clause type files."""
    clause_types = []
    by_type_path = CLAUSES_PATH / "by_type"

    if by_type_path.exists():
        for json_file in by_type_path.glob("*.json"):
            clause_data = _load_json_file(json_file)
            if clause_data:
                clause_types.append(clause_data)

    return clause_types


def _get_lines_of_business() -> List[Dict[str, Any]]:
    """Get all available lines of business with metadata."""
    lines = []

    # Define line metadata
    line_metadata = {
        "aviation": {
            "display_name": "Aviation",
            "description": "Aviation hull, liability, and related insurance products"
        },
        "casualty": {
            "display_name": "Casualty",
            "description": "General liability, professional liability, and casualty insurance"
        },
        "commercial": {
            "display_name": "Commercial",
            "description": "Commercial property and combined business insurance"
        },
        "cyber": {
            "display_name": "Cyber",
            "description": "Cyber liability, data breach, and network security insurance"
        },
        "marine": {
            "display_name": "Marine",
            "description": "Marine cargo, hull, and marine liability insurance"
        },
        "motor": {
            "display_name": "Motor",
            "description": "Motor vehicle and fleet insurance products"
        },
        "property": {
            "display_name": "Property",
            "description": "Property all risks, fire, and related insurance"
        },
        "specialty": {
            "display_name": "Specialty",
            "description": "Specialty lines including fine art, political risk, and niche products"
        }
    }

    # Get clause types
    clause_types = [
        "indemnification", "limitation_of_liability", "exclusions",
        "warranties", "conditions", "definitions", "subrogation"
    ]

    if POLICIES_PATH.exists():
        for line_dir in POLICIES_PATH.iterdir():
            if line_dir.is_dir():
                line_id = line_dir.name
                metadata = line_metadata.get(line_id, {
                    "display_name": line_id.replace("_", " ").title(),
                    "description": f"{line_id.replace('_', ' ').title()} insurance products"
                })

                # Count policies
                policy_count = len(list(line_dir.glob("*.json")))

                lines.append({
                    "id": line_id,
                    "name": line_id,
                    "display_name": metadata["display_name"],
                    "description": metadata["description"],
                    "policy_count": policy_count,
                    "clause_types": clause_types
                })

    # Sort by display name
    lines.sort(key=lambda x: x["display_name"])

    return lines


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/policies", response_model=PolicyTemplatesResponse)
async def get_policy_templates(
    line: Optional[str] = Query(None, description="Line of business to filter by")
) -> PolicyTemplatesResponse:
    """
    Get policy templates, optionally filtered by line of business.

    Args:
        line: Optional line of business filter (e.g., 'cyber', 'marine', 'property')

    Returns:
        PolicyTemplatesResponse with list of policy templates.
    """
    if line:
        # Validate line exists
        line_path = POLICIES_PATH / line
        if not line_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Line of business '{line}' not found. Use /templates/lines to see available options."
            )

        policies = _load_policies_for_line(line)
    else:
        policies = _load_all_policies()

    templates = [
        PolicyTemplateBase(
            id=p.get("id", ""),
            name=p.get("name", ""),
            category=p.get("category", ""),
            line_of_business=p.get("line_of_business", p.get("category", "")),
            description=p.get("description", ""),
            insurer=p.get("insurer"),
            form_number=p.get("form_number"),
            tags=p.get("tags", [])
        )
        for p in policies
    ]

    return PolicyTemplatesResponse(
        count=len(templates),
        line_of_business=line,
        templates=templates
    )


@router.get("/policies/{policy_id}", response_model=PolicyTemplateDetail)
async def get_policy_template(policy_id: str) -> PolicyTemplateDetail:
    """
    Get detailed policy template by ID.

    Args:
        policy_id: The policy template identifier.

    Returns:
        PolicyTemplateDetail with full template information.

    Raises:
        HTTPException: If policy template not found.
    """
    # Search through all policies
    all_policies = _load_all_policies()

    for policy in all_policies:
        if policy.get("id") == policy_id:
            return PolicyTemplateDetail(
                id=policy.get("id", ""),
                name=policy.get("name", ""),
                category=policy.get("category", ""),
                line_of_business=policy.get("line_of_business", policy.get("category", "")),
                description=policy.get("description", ""),
                insurer=policy.get("insurer"),
                form_number=policy.get("form_number"),
                tags=policy.get("tags", []),
                sections=policy.get("sections", []),
                variables=policy.get("variables", []),
                source=policy.get("source"),
                effective_date=policy.get("effective_date")
            )

    raise HTTPException(
        status_code=404,
        detail=f"Policy template '{policy_id}' not found"
    )


@router.get("/clauses", response_model=ClausesResponse)
async def get_clauses(
    type: Optional[str] = Query(None, alias="type", description="Clause type filter"),
    line: Optional[str] = Query(None, description="Line of business filter")
) -> ClausesResponse:
    """
    Get clauses, optionally filtered by type and line of business.

    Args:
        type: Clause type filter (e.g., 'exclusions', 'conditions', 'warranties')
        line: Line of business filter (e.g., 'general', 'marine', 'cyber')

    Returns:
        ClausesResponse with list of clauses.
    """
    all_clauses: List[ClauseDetail] = []

    if type:
        # Load specific clause type
        clause_data = _load_clauses_by_type(type)
        if not clause_data:
            raise HTTPException(
                status_code=404,
                detail=f"Clause type '{type}' not found. Available types: exclusions, conditions, warranties, indemnification, limitation_of_liability, definitions, subrogation"
            )

        for clause in clause_data.get("clauses", []):
            # Filter by line if specified
            clause_line = clause.get("line_of_business", "general")
            if line and clause_line != line and clause_line != "general":
                continue

            all_clauses.append(ClauseDetail(
                id=clause.get("id", ""),
                name=clause.get("name", ""),
                text=clause.get("text", ""),
                typical_use=clause.get("typical_use"),
                line_of_business=clause_line,
                source=clause.get("source")
            ))
    else:
        # Load all clause types
        clause_types = _load_all_clause_types()

        for clause_type_data in clause_types:
            for clause in clause_type_data.get("clauses", []):
                # Filter by line if specified
                clause_line = clause.get("line_of_business", "general")
                if line and clause_line != line and clause_line != "general":
                    continue

                all_clauses.append(ClauseDetail(
                    id=clause.get("id", ""),
                    name=clause.get("name", ""),
                    text=clause.get("text", ""),
                    typical_use=clause.get("typical_use"),
                    line_of_business=clause_line,
                    source=clause.get("source")
                ))

    return ClausesResponse(
        count=len(all_clauses),
        clause_type=type,
        line_of_business=line,
        clauses=all_clauses
    )


@router.get("/clauses/types")
async def get_clause_types() -> Dict[str, Any]:
    """
    Get all available clause types with summary.

    Returns:
        Dictionary with clause types and their counts.
    """
    clause_types = _load_all_clause_types()

    types_summary = []
    for ct in clause_types:
        types_summary.append({
            "id": ct.get("id", ""),
            "name": ct.get("name", ""),
            "type": ct.get("type", ""),
            "description": ct.get("description", ""),
            "total_clauses": ct.get("total_clauses", len(ct.get("clauses", []))),
            "tags": ct.get("tags", [])
        })

    return {
        "count": len(types_summary),
        "types": types_summary
    }


@router.get("/clauses/{clause_id}")
async def get_clause_by_id(clause_id: str) -> ClauseDetail:
    """
    Get a specific clause by its ID.

    Args:
        clause_id: The clause identifier.

    Returns:
        ClauseDetail with full clause information.

    Raises:
        HTTPException: If clause not found.
    """
    clause_types = _load_all_clause_types()

    for clause_type_data in clause_types:
        for clause in clause_type_data.get("clauses", []):
            if clause.get("id") == clause_id:
                return ClauseDetail(
                    id=clause.get("id", ""),
                    name=clause.get("name", ""),
                    text=clause.get("text", ""),
                    typical_use=clause.get("typical_use"),
                    line_of_business=clause.get("line_of_business", "general"),
                    source=clause.get("source")
                )

    raise HTTPException(
        status_code=404,
        detail=f"Clause '{clause_id}' not found"
    )


@router.get("/forms/{form_type}", response_model=FormTemplateResponse)
async def get_form_template(form_type: str) -> FormTemplateResponse:
    """
    Get form template by type.

    Args:
        form_type: The form type identifier (e.g., 'proposal', 'claim', 'endorsement')

    Returns:
        FormTemplateResponse with form template.

    Raises:
        HTTPException: If form template not found.
    """
    # Define standard form templates
    standard_forms = {
        "proposal": {
            "id": "form_proposal",
            "name": "Insurance Proposal Form",
            "form_type": "proposal",
            "description": "Standard insurance proposal form for collecting risk information",
            "fields": [
                {"name": "proposer_name", "type": "text", "label": "Proposer Name", "required": True},
                {"name": "proposer_address", "type": "textarea", "label": "Address", "required": True},
                {"name": "business_description", "type": "textarea", "label": "Business Description", "required": True},
                {"name": "sum_insured", "type": "currency", "label": "Sum Insured", "required": True},
                {"name": "inception_date", "type": "date", "label": "Requested Inception Date", "required": True},
                {"name": "expiry_date", "type": "date", "label": "Requested Expiry Date", "required": True},
                {"name": "previous_insurance", "type": "boolean", "label": "Previous Insurance?", "required": True},
                {"name": "previous_claims", "type": "textarea", "label": "Previous Claims History", "required": False},
                {"name": "special_conditions", "type": "textarea", "label": "Special Conditions Required", "required": False}
            ]
        },
        "claim": {
            "id": "form_claim",
            "name": "Insurance Claim Form",
            "form_type": "claim",
            "description": "Standard insurance claim notification form",
            "fields": [
                {"name": "policy_number", "type": "text", "label": "Policy Number", "required": True},
                {"name": "insured_name", "type": "text", "label": "Insured Name", "required": True},
                {"name": "date_of_loss", "type": "date", "label": "Date of Loss", "required": True},
                {"name": "time_of_loss", "type": "time", "label": "Time of Loss", "required": False},
                {"name": "location_of_loss", "type": "textarea", "label": "Location of Loss", "required": True},
                {"name": "description_of_loss", "type": "textarea", "label": "Description of Loss/Damage", "required": True},
                {"name": "estimated_value", "type": "currency", "label": "Estimated Value of Claim", "required": True},
                {"name": "police_report", "type": "boolean", "label": "Police Report Filed?", "required": True},
                {"name": "police_reference", "type": "text", "label": "Police Reference Number", "required": False},
                {"name": "witnesses", "type": "textarea", "label": "Witness Details", "required": False},
                {"name": "supporting_documents", "type": "file", "label": "Supporting Documents", "required": False}
            ]
        },
        "endorsement": {
            "id": "form_endorsement",
            "name": "Policy Endorsement Request",
            "form_type": "endorsement",
            "description": "Form for requesting policy amendments and endorsements",
            "fields": [
                {"name": "policy_number", "type": "text", "label": "Policy Number", "required": True},
                {"name": "insured_name", "type": "text", "label": "Insured Name", "required": True},
                {"name": "endorsement_type", "type": "select", "label": "Endorsement Type", "required": True,
                 "options": ["Address Change", "Sum Insured Change", "Additional Interest", "Name Change", "Coverage Extension", "Other"]},
                {"name": "effective_date", "type": "date", "label": "Effective Date", "required": True},
                {"name": "current_details", "type": "textarea", "label": "Current Policy Details", "required": True},
                {"name": "requested_changes", "type": "textarea", "label": "Requested Changes", "required": True},
                {"name": "reason_for_change", "type": "textarea", "label": "Reason for Change", "required": False}
            ]
        },
        "certificate": {
            "id": "form_certificate",
            "name": "Certificate of Insurance Request",
            "form_type": "certificate",
            "description": "Form for requesting certificate of insurance",
            "fields": [
                {"name": "policy_number", "type": "text", "label": "Policy Number", "required": True},
                {"name": "insured_name", "type": "text", "label": "Named Insured", "required": True},
                {"name": "certificate_holder", "type": "text", "label": "Certificate Holder Name", "required": True},
                {"name": "certificate_holder_address", "type": "textarea", "label": "Certificate Holder Address", "required": True},
                {"name": "description_of_operations", "type": "textarea", "label": "Description of Operations", "required": True},
                {"name": "additional_insured", "type": "boolean", "label": "Additional Insured Status Required?", "required": True},
                {"name": "waiver_of_subrogation", "type": "boolean", "label": "Waiver of Subrogation Required?", "required": True},
                {"name": "special_requirements", "type": "textarea", "label": "Special Requirements", "required": False}
            ]
        },
        "renewal": {
            "id": "form_renewal",
            "name": "Policy Renewal Form",
            "form_type": "renewal",
            "description": "Form for policy renewal processing",
            "fields": [
                {"name": "policy_number", "type": "text", "label": "Expiring Policy Number", "required": True},
                {"name": "insured_name", "type": "text", "label": "Insured Name", "required": True},
                {"name": "current_expiry", "type": "date", "label": "Current Expiry Date", "required": True},
                {"name": "renewal_period", "type": "select", "label": "Renewal Period", "required": True,
                 "options": ["12 months", "18 months", "24 months", "36 months"]},
                {"name": "changes_required", "type": "boolean", "label": "Any Changes Required?", "required": True},
                {"name": "change_details", "type": "textarea", "label": "Details of Changes", "required": False},
                {"name": "claims_in_period", "type": "boolean", "label": "Any Claims in Current Period?", "required": True},
                {"name": "claim_details", "type": "textarea", "label": "Claim Details", "required": False}
            ]
        }
    }

    # Check for file-based form first
    form_file = FORMS_PATH / f"{form_type}.json"
    if form_file.exists():
        form_data = _load_json_file(form_file)
        if form_data:
            return FormTemplateResponse(
                form=FormTemplate(
                    id=form_data.get("id", f"form_{form_type}"),
                    name=form_data.get("name", form_type.title()),
                    form_type=form_type,
                    description=form_data.get("description", ""),
                    fields=form_data.get("fields", [])
                )
            )

    # Use standard forms
    if form_type in standard_forms:
        form_data = standard_forms[form_type]
        return FormTemplateResponse(
            form=FormTemplate(
                id=form_data["id"],
                name=form_data["name"],
                form_type=form_data["form_type"],
                description=form_data["description"],
                fields=form_data["fields"]
            )
        )

    raise HTTPException(
        status_code=404,
        detail=f"Form type '{form_type}' not found. Available types: proposal, claim, endorsement, certificate, renewal"
    )


@router.get("/forms")
async def list_form_types() -> Dict[str, Any]:
    """
    List all available form types.

    Returns:
        Dictionary with available form types.
    """
    form_types = [
        {"type": "proposal", "name": "Insurance Proposal Form", "description": "Standard insurance proposal form"},
        {"type": "claim", "name": "Insurance Claim Form", "description": "Standard claim notification form"},
        {"type": "endorsement", "name": "Policy Endorsement Request", "description": "Policy amendment request form"},
        {"type": "certificate", "name": "Certificate of Insurance Request", "description": "COI request form"},
        {"type": "renewal", "name": "Policy Renewal Form", "description": "Policy renewal processing form"}
    ]

    return {
        "count": len(form_types),
        "form_types": form_types
    }


@router.get("/lines", response_model=LinesOfBusinessResponse)
async def get_lines_of_business() -> LinesOfBusinessResponse:
    """
    Get all available lines of business.

    Returns:
        LinesOfBusinessResponse with list of lines of business.
    """
    lines_data = _get_lines_of_business()

    lines = [
        LineOfBusiness(
            id=line["id"],
            name=line["name"],
            display_name=line["display_name"],
            description=line["description"],
            policy_count=line["policy_count"],
            clause_types=line["clause_types"]
        )
        for line in lines_data
    ]

    return LinesOfBusinessResponse(
        count=len(lines),
        lines=lines
    )


# =============================================================================
# Document Sections Schema and Endpoint
# =============================================================================

class SectionDefinition(BaseModel):
    """A document section definition."""
    id: str
    name: str
    description: str
    required: bool = False
    default_enabled: bool = True
    order: int = 0


class SectionsCategory(BaseModel):
    """A category of sections (e.g., core, exclusions, conditions)."""
    id: str
    name: str
    description: str
    sections: List[SectionDefinition]


class DocumentSectionsResponse(BaseModel):
    """Response for document sections."""
    document_type: str
    line_of_business: str
    categories: List[SectionsCategory]
    total_sections: int


def _get_sections_for_line_of_business(line: str, doc_type: str) -> List[SectionsCategory]:
    """Get document sections based on line of business and document type."""

    # Define sections by line of business
    sections_by_line = {
        "property": {
            "core": [
                {"id": "declarations", "name": "Declarations Page", "description": "Named insured, policy period, limits, and deductibles", "required": True, "order": 1},
                {"id": "insuring_agreement", "name": "Insuring Agreement", "description": "Core coverage grant and insured perils", "required": True, "order": 2},
                {"id": "definitions", "name": "Definitions", "description": "Key terms used throughout the policy", "required": True, "order": 3},
                {"id": "coverage_building", "name": "Building Coverage", "description": "Coverage for insured buildings and structures", "required": False, "order": 4},
                {"id": "coverage_bpp", "name": "Business Personal Property", "description": "Coverage for furniture, fixtures, equipment, and inventory", "required": False, "order": 5},
                {"id": "coverage_business_income", "name": "Business Income", "description": "Coverage for lost income due to covered loss", "required": False, "order": 6},
                {"id": "coverage_extra_expense", "name": "Extra Expense", "description": "Coverage for additional costs to minimize business interruption", "required": False, "order": 7},
                {"id": "schedule", "name": "Schedule of Covered Locations", "description": "List of insured locations with values", "required": True, "order": 8},
            ],
            "exclusions": [
                {"id": "exc_war", "name": "War & Terrorism", "description": "Exclusion for war, terrorism, and military action", "required": True, "order": 1},
                {"id": "exc_nuclear", "name": "Nuclear Hazard", "description": "Exclusion for nuclear reaction, radiation, or contamination", "required": True, "order": 2},
                {"id": "exc_earth_movement", "name": "Earth Movement", "description": "Exclusion for earthquake, landslide, etc. (unless endorsed)", "required": False, "order": 3},
                {"id": "exc_flood", "name": "Flood", "description": "Exclusion for flood damage (unless endorsed)", "required": False, "order": 4},
                {"id": "exc_ordinance_law", "name": "Ordinance or Law", "description": "Exclusion for increased cost due to building codes", "required": False, "order": 5},
                {"id": "exc_intentional_loss", "name": "Intentional Loss", "description": "Exclusion for intentional damage by insured", "required": True, "order": 6},
            ],
            "conditions": [
                {"id": "cond_notice", "name": "Notice of Claim", "description": "Requirements for notifying insurer of loss", "required": True, "order": 1},
                {"id": "cond_duties", "name": "Duties After Loss", "description": "Insured's obligations following a covered loss", "required": True, "order": 2},
                {"id": "cond_valuation", "name": "Valuation", "description": "How covered property is valued for loss settlement", "required": True, "order": 3},
                {"id": "cond_coinsurance", "name": "Coinsurance", "description": "Coinsurance requirement and penalty calculation", "required": False, "order": 4},
                {"id": "cond_subrogation", "name": "Subrogation", "description": "Insurer's right to pursue third parties", "required": True, "order": 5},
                {"id": "cond_cancellation", "name": "Cancellation", "description": "Policy cancellation terms and procedures", "required": True, "order": 6},
            ]
        },
        "cyber": {
            "core": [
                {"id": "declarations", "name": "Declarations Page", "description": "Named insured, policy period, limits, and retentions", "required": True, "order": 1},
                {"id": "insuring_agreement", "name": "Insuring Agreement", "description": "Core coverage grants for cyber incidents", "required": True, "order": 2},
                {"id": "definitions", "name": "Definitions", "description": "Cyber-specific terminology definitions", "required": True, "order": 3},
                {"id": "coverage_security_privacy", "name": "Security & Privacy Liability", "description": "Third-party claims for data breaches", "required": False, "order": 4},
                {"id": "coverage_media_liability", "name": "Media Liability", "description": "Coverage for content-related claims", "required": False, "order": 5},
                {"id": "coverage_network_interruption", "name": "Network Interruption", "description": "Business income loss from cyber events", "required": False, "order": 6},
                {"id": "coverage_data_restoration", "name": "Data Restoration", "description": "Costs to restore corrupted or lost data", "required": False, "order": 7},
                {"id": "coverage_cyber_extortion", "name": "Cyber Extortion", "description": "Ransomware and extortion payments", "required": False, "order": 8},
                {"id": "coverage_breach_response", "name": "Breach Response", "description": "Forensics, notification, credit monitoring", "required": False, "order": 9},
                {"id": "schedule", "name": "Schedule of Coverage", "description": "Coverage limits and retentions by insuring agreement", "required": True, "order": 10},
            ],
            "exclusions": [
                {"id": "exc_war_terrorism", "name": "War & Terrorism", "description": "Exclusion for war, cyber terrorism by state actors", "required": True, "order": 1},
                {"id": "exc_prior_acts", "name": "Prior Acts", "description": "Incidents occurring before retroactive date", "required": True, "order": 2},
                {"id": "exc_bodily_injury", "name": "Bodily Injury/Property Damage", "description": "Physical injury or tangible property damage", "required": True, "order": 3},
                {"id": "exc_infrastructure", "name": "Infrastructure Failure", "description": "Exclusion for utility or internet outages", "required": False, "order": 4},
                {"id": "exc_contractual", "name": "Contractual Liability", "description": "Assumed liability under contract", "required": False, "order": 5},
                {"id": "exc_unencrypted", "name": "Unencrypted Devices", "description": "Breaches from unencrypted portable devices", "required": False, "order": 6},
                {"id": "exc_failure_to_maintain", "name": "Failure to Maintain Security", "description": "Known security vulnerabilities not patched", "required": False, "order": 7},
            ],
            "conditions": [
                {"id": "cond_notice", "name": "Notice of Claim", "description": "Requirements for reporting cyber incidents", "required": True, "order": 1},
                {"id": "cond_cooperation", "name": "Cooperation", "description": "Insured's duty to cooperate in defense", "required": True, "order": 2},
                {"id": "cond_consent_settlement", "name": "Consent to Settle", "description": "Approval required for settlements", "required": True, "order": 3},
                {"id": "cond_panel_vendors", "name": "Panel Vendors", "description": "Use of pre-approved breach response vendors", "required": False, "order": 4},
                {"id": "cond_subrogation", "name": "Subrogation", "description": "Insurer's right to pursue third parties", "required": True, "order": 5},
                {"id": "cond_other_insurance", "name": "Other Insurance", "description": "Coordination with other policies", "required": True, "order": 6},
            ]
        },
        "marine": {
            "core": [
                {"id": "declarations", "name": "Declarations", "description": "Schedule of vessels, values, and trading limits", "required": True, "order": 1},
                {"id": "insuring_agreement", "name": "Insuring Agreement", "description": "Core coverage grant for marine perils", "required": True, "order": 2},
                {"id": "definitions", "name": "Definitions", "description": "Marine and shipping terminology", "required": True, "order": 3},
                {"id": "coverage_hull", "name": "Hull & Machinery", "description": "Coverage for vessel, engines, equipment", "required": False, "order": 4},
                {"id": "coverage_cargo", "name": "Cargo", "description": "Coverage for goods in transit", "required": False, "order": 5},
                {"id": "coverage_pi", "name": "P&I (Protection & Indemnity)", "description": "Third party liability coverage", "required": False, "order": 6},
                {"id": "coverage_freight", "name": "Freight", "description": "Coverage for freight revenue", "required": False, "order": 7},
                {"id": "coverage_war_risks", "name": "War Risks", "description": "Coverage for war perils at sea", "required": False, "order": 8},
                {"id": "schedule_vessels", "name": "Schedule of Vessels", "description": "List of insured vessels with details", "required": True, "order": 9},
            ],
            "exclusions": [
                {"id": "exc_wear_tear", "name": "Wear and Tear", "description": "Ordinary wear, deterioration, and maintenance", "required": True, "order": 1},
                {"id": "exc_inherent_vice", "name": "Inherent Vice", "description": "Natural deterioration of cargo", "required": True, "order": 2},
                {"id": "exc_delay", "name": "Delay", "description": "Loss caused by delay", "required": True, "order": 3},
                {"id": "exc_insolvency", "name": "Insolvency", "description": "Financial failure of shipowners/charterers", "required": False, "order": 4},
                {"id": "exc_unseaworthiness", "name": "Unseaworthiness", "description": "Vessel unfit for voyage (with privity)", "required": False, "order": 5},
                {"id": "exc_radioactive", "name": "Radioactive Contamination", "description": "Nuclear and radioactive exclusions", "required": True, "order": 6},
            ],
            "conditions": [
                {"id": "cond_notice", "name": "Notice of Loss", "description": "Immediate notice of marine casualties", "required": True, "order": 1},
                {"id": "cond_sue_labour", "name": "Sue and Labour", "description": "Duty to mitigate and recover costs", "required": True, "order": 2},
                {"id": "cond_general_average", "name": "General Average", "description": "Contribution to general average", "required": True, "order": 3},
                {"id": "cond_subrogation", "name": "Subrogation", "description": "Insurer's right of recovery", "required": True, "order": 4},
                {"id": "cond_classification", "name": "Classification", "description": "Maintenance of vessel classification", "required": True, "order": 5},
                {"id": "cond_trading_limits", "name": "Trading Limits", "description": "Geographic and voyage restrictions", "required": True, "order": 6},
            ]
        },
        "casualty": {
            "core": [
                {"id": "declarations", "name": "Declarations Page", "description": "Named insured, limits, and policy details", "required": True, "order": 1},
                {"id": "insuring_agreement", "name": "Insuring Agreement", "description": "General liability coverage grant", "required": True, "order": 2},
                {"id": "definitions", "name": "Definitions", "description": "Key policy terms and definitions", "required": True, "order": 3},
                {"id": "coverage_bodily_injury", "name": "Bodily Injury Liability", "description": "Coverage for third party bodily injury", "required": False, "order": 4},
                {"id": "coverage_property_damage", "name": "Property Damage Liability", "description": "Coverage for third party property damage", "required": False, "order": 5},
                {"id": "coverage_personal_injury", "name": "Personal & Advertising Injury", "description": "Coverage for defamation, invasion of privacy", "required": False, "order": 6},
                {"id": "coverage_products", "name": "Products/Completed Operations", "description": "Coverage for products liability", "required": False, "order": 7},
                {"id": "coverage_medical", "name": "Medical Payments", "description": "Medical expenses regardless of liability", "required": False, "order": 8},
            ],
            "exclusions": [
                {"id": "exc_expected_intended", "name": "Expected or Intended Injury", "description": "Intentional acts exclusion", "required": True, "order": 1},
                {"id": "exc_contractual", "name": "Contractual Liability", "description": "Assumed contractual liability", "required": False, "order": 2},
                {"id": "exc_liquor", "name": "Liquor Liability", "description": "Serving or selling alcohol", "required": False, "order": 3},
                {"id": "exc_pollution", "name": "Pollution", "description": "Pollution and contamination exclusion", "required": True, "order": 4},
                {"id": "exc_professional", "name": "Professional Liability", "description": "Professional services errors", "required": False, "order": 5},
                {"id": "exc_auto", "name": "Auto Liability", "description": "Use of automobiles", "required": True, "order": 6},
            ],
            "conditions": [
                {"id": "cond_notice", "name": "Notice of Occurrence", "description": "Duty to report claims and occurrences", "required": True, "order": 1},
                {"id": "cond_cooperation", "name": "Cooperation", "description": "Insured's duty to cooperate", "required": True, "order": 2},
                {"id": "cond_legal_action", "name": "Legal Action Against Us", "description": "Conditions for suit against insurer", "required": True, "order": 3},
                {"id": "cond_other_insurance", "name": "Other Insurance", "description": "Coordination with other policies", "required": True, "order": 4},
                {"id": "cond_duties_event", "name": "Duties in Event of Occurrence", "description": "Required actions after incident", "required": True, "order": 5},
            ]
        }
    }

    # Default sections for unspecified lines
    default_sections = {
        "core": [
            {"id": "declarations", "name": "Declarations Page", "description": "Named insured, policy period, limits", "required": True, "order": 1},
            {"id": "insuring_agreement", "name": "Insuring Agreement", "description": "Core coverage grant", "required": True, "order": 2},
            {"id": "definitions", "name": "Definitions", "description": "Key terms and definitions", "required": True, "order": 3},
            {"id": "coverage_a", "name": "Coverage A", "description": "Primary coverage section", "required": False, "order": 4},
            {"id": "coverage_b", "name": "Coverage B", "description": "Secondary coverage section", "required": False, "order": 5},
            {"id": "coverage_c", "name": "Coverage C", "description": "Additional coverage section", "required": False, "order": 6},
            {"id": "schedule", "name": "Schedule", "description": "Policy schedule", "required": True, "order": 7},
        ],
        "exclusions": [
            {"id": "exc_war", "name": "War & Terrorism", "description": "War exclusion", "required": True, "order": 1},
            {"id": "exc_prior_acts", "name": "Prior Acts", "description": "Prior acts exclusion", "required": False, "order": 2},
            {"id": "exc_intentional", "name": "Intentional Acts", "description": "Intentional acts exclusion", "required": True, "order": 3},
        ],
        "conditions": [
            {"id": "cond_notice", "name": "Notice of Claim", "description": "Claim notification requirements", "required": True, "order": 1},
            {"id": "cond_cooperation", "name": "Cooperation", "description": "Duty to cooperate", "required": True, "order": 2},
            {"id": "cond_subrogation", "name": "Subrogation", "description": "Subrogation rights", "required": True, "order": 3},
            {"id": "cond_cancellation", "name": "Cancellation", "description": "Cancellation terms", "required": True, "order": 4},
        ]
    }

    # Get sections for the specified line, or use default
    line_lower = line.lower() if line else ""
    sections_data = sections_by_line.get(line_lower, default_sections)

    # Build categories response
    categories = []

    category_metadata = {
        "core": {"name": "Core Policy Sections", "description": "Essential policy sections that define coverage"},
        "exclusions": {"name": "Exclusions", "description": "Risks and situations not covered by the policy"},
        "conditions": {"name": "Conditions", "description": "Requirements and duties that apply to the policy"}
    }

    for cat_id, sections in sections_data.items():
        cat_meta = category_metadata.get(cat_id, {"name": cat_id.title(), "description": ""})
        categories.append(SectionsCategory(
            id=cat_id,
            name=cat_meta["name"],
            description=cat_meta["description"],
            sections=[SectionDefinition(**s) for s in sections]
        ))

    return categories


@router.get("/sections", response_model=DocumentSectionsResponse)
async def get_document_sections(
    line_of_business: str = Query(..., description="Line of business (e.g., 'property', 'cyber', 'marine')"),
    document_type: str = Query("policy", description="Document type (e.g., 'policy', 'endorsement', 'schedule')")
) -> DocumentSectionsResponse:
    """
    Get dynamic document sections based on line of business and document type.

    Returns structured sections organized by category (core, exclusions, conditions).
    Each section includes whether it's required and enabled by default.

    Args:
        line_of_business: The line of business (property, cyber, marine, casualty, etc.)
        document_type: The type of document being generated

    Returns:
        DocumentSectionsResponse with categorized sections.
    """
    categories = _get_sections_for_line_of_business(line_of_business, document_type)

    total_sections = sum(len(cat.sections) for cat in categories)

    return DocumentSectionsResponse(
        document_type=document_type,
        line_of_business=line_of_business,
        categories=categories,
        total_sections=total_sections
    )


@router.get("/search")
async def search_templates(
    q: str = Query(..., min_length=2, description="Search query"),
    search_in: str = Query("all", description="Search in: all, policies, clauses")
) -> Dict[str, Any]:
    """
    Search across templates and clauses.

    Args:
        q: Search query (minimum 2 characters)
        search_in: What to search in (all, policies, clauses)

    Returns:
        Search results with matching templates and clauses.
    """
    q_lower = q.lower()
    results = {
        "query": q,
        "policies": [],
        "clauses": []
    }

    # Search policies
    if search_in in ("all", "policies"):
        all_policies = _load_all_policies()
        for policy in all_policies:
            # Search in name, description, and tags
            searchable = f"{policy.get('name', '')} {policy.get('description', '')} {' '.join(policy.get('tags', []))}".lower()
            if q_lower in searchable:
                results["policies"].append({
                    "id": policy.get("id", ""),
                    "name": policy.get("name", ""),
                    "category": policy.get("category", ""),
                    "line_of_business": policy.get("line_of_business", ""),
                    "match_type": "policy"
                })

    # Search clauses
    if search_in in ("all", "clauses"):
        clause_types = _load_all_clause_types()
        for clause_type_data in clause_types:
            for clause in clause_type_data.get("clauses", []):
                # Search in name and text
                searchable = f"{clause.get('name', '')} {clause.get('text', '')}".lower()
                if q_lower in searchable:
                    results["clauses"].append({
                        "id": clause.get("id", ""),
                        "name": clause.get("name", ""),
                        "line_of_business": clause.get("line_of_business", "general"),
                        "clause_type": clause_type_data.get("type", ""),
                        "match_type": "clause"
                    })

    results["total_policies"] = len(results["policies"])
    results["total_clauses"] = len(results["clauses"])
    results["total"] = results["total_policies"] + results["total_clauses"]

    return results
