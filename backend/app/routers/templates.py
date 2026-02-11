"""
Templates Router - Industry Standard Insurance Document Templates

Provides access to Lloyd's market and commercial insurance templates
with preview, download, and copy-to-own functionality.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from io import BytesIO

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.template import Template, TemplateFavorite
from app.services.insurance_templates import (
    TEMPLATE_CATEGORIES,
    INSURANCE_TEMPLATES,
    STANDARD_CLAUSES,
    get_all_templates,
    get_template,
    get_template_content,
    get_templates_by_category,
    get_standard_clause,
    get_all_standard_clauses,
    auto_select_template,
    render_template,
    get_template_field_count,
    validate_template_data,
)

router = APIRouter()


@router.get("/categories")
async def list_categories():
    """Get all template categories."""
    return {
        "categories": TEMPLATE_CATEGORIES
    }


@router.get("/clauses")
async def list_standard_clauses():
    """Get all standard Lloyd's market clauses (LMA/NMA)."""
    clauses = get_all_standard_clauses()
    return {
        "count": len(clauses),
        "clauses": [
            {
                "key": key,
                "id": clause["id"],
                "name": clause["name"],
            }
            for key, clause in clauses.items()
        ]
    }


@router.get("/clauses/{clause_key}")
async def get_clause(clause_key: str):
    """Get a specific standard clause with full text."""
    clause = get_standard_clause(clause_key)
    if not clause:
        raise HTTPException(404, f"Clause '{clause_key}' not found")
    return clause


@router.get("/")
async def list_templates(category: Optional[str] = None):
    """
    Get all available insurance document templates.

    Args:
        category: Optional filter by category (lloyds, commercial, specialty, marine)
    """
    if category:
        templates = get_templates_by_category(category)
        templates = [
            {
                "id": t["id"],
                "name": t["name"],
                "category": t["category"],
                "description": t["description"],
                "version": t.get("version", "1.0"),
                "tags": t.get("tags", []),
                "sections": t.get("sections", []),
                "is_system": t.get("is_system", True),
                "has_content_template": "content_template" in t,
            }
            for t in templates
        ]
    else:
        templates = get_all_templates()

    return {
        "count": len(templates),
        "templates": templates
    }


@router.get("/{template_id}")
async def get_template_details(template_id: str):
    """
    Get full template details including all fields.

    Args:
        template_id: The template identifier
    """
    template = get_template(template_id)

    if not template:
        raise HTTPException(404, f"Template '{template_id}' not found")

    return template


@router.post("/auto-select")
async def auto_select(document_type: Optional[str] = None, risk_type: Optional[str] = None):
    """
    Auto-select the most appropriate template based on document type and risk.

    Args:
        document_type: Type of document (slip, policy, certificate, etc.)
        risk_type: Type of risk (cyber, property, marine, lloyds, etc.)

    Returns:
        The recommended template based on the criteria.
    """
    template_id = auto_select_template(risk_type or "", document_type)
    template = get_template(template_id)

    if template:
        return {
            "selected_template": template_id,
            "template": {
                "id": template["id"],
                "name": template["name"],
                "category": template["category"],
                "description": template["description"],
                "field_count": get_template_field_count(template_id),
            },
            "reason": f"Auto-selected based on" + (f" risk type: {risk_type}" if risk_type else "") + (f" document type: {document_type}" if document_type else "")
        }

    raise HTTPException(404, "No suitable template found")


@router.get("/{template_id}/preview")
async def preview_template(template_id: str):
    """
    Get a preview of the template with sample data filled in.
    Returns the full rendered document content.
    """
    template = get_template(template_id)

    if not template:
        raise HTTPException(404, f"Template '{template_id}' not found")

    # Generate sample data
    sample_data = _generate_sample_data(template)

    # Render the template with sample data
    rendered_content = render_template(template_id, sample_data)

    return {
        "template_id": template_id,
        "template_name": template["name"],
        "category": template["category"],
        "version": template.get("version", "1.0"),
        "sections": template.get("sections", []),
        "sample_data": sample_data,
        "rendered_content": rendered_content,
        "has_full_content": bool(rendered_content),
    }


@router.get("/{template_id}/content")
async def get_template_raw_content(template_id: str):
    """
    Get the raw template content (unrendered with placeholders).
    Useful for editing/customization.
    """
    template = get_template(template_id)

    if not template:
        raise HTTPException(404, f"Template '{template_id}' not found")

    content = get_template_content(template_id)

    return {
        "template_id": template_id,
        "template_name": template["name"],
        "content": content,
        "fields": template.get("fields", {}),
        "sections": template.get("sections", []),
        "standard_clauses": template.get("standard_clauses", []),
    }


@router.get("/{template_id}/download")
async def download_template(
    template_id: str,
    format: str = "txt",
    filled: bool = False
):
    """
    Download the template as a file.

    Args:
        template_id: The template identifier
        format: Output format (txt, pdf, docx) - currently supports txt
        filled: If True, fills with sample data; if False, keeps placeholders
    """
    template = get_template(template_id)

    if not template:
        raise HTTPException(404, f"Template '{template_id}' not found")

    if filled:
        sample_data = _generate_sample_data(template)
        content = render_template(template_id, sample_data)
    else:
        content = get_template_content(template_id)

    if not content:
        raise HTTPException(404, "Template has no content to download")

    # For now, support text format. PDF/DOCX can be added later
    if format == "txt":
        filename = f"{template_id}.txt"
        media_type = "text/plain"
    elif format == "pdf":
        # TODO: Implement PDF generation
        filename = f"{template_id}.txt"
        media_type = "text/plain"
        content = f"# PDF Export - Coming Soon\n\n{content}"
    elif format == "docx":
        # TODO: Implement DOCX generation
        filename = f"{template_id}.txt"
        media_type = "text/plain"
        content = f"# DOCX Export - Coming Soon\n\n{content}"
    else:
        filename = f"{template_id}.txt"
        media_type = "text/plain"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/{template_id}/copy")
async def copy_template_to_user(
    template_id: str,
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Copy a system template to user's own templates for customization.

    Args:
        template_id: The system template to copy
        name: Optional custom name for the copy
    """
    # Get the system template
    system_template = get_template(template_id)

    if not system_template:
        raise HTTPException(404, f"Template '{template_id}' not found")

    # Create a unique key for the user's copy
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new_key = f"user_{current_user.id}_{template_id}_{timestamp}"

    # Create the user template
    user_template = Template(
        template_key=new_key,
        name=name or f"My {system_template['name']}",
        description=f"Customized copy of {system_template['name']}",
        version="1.0",
        category="custom",
        document_type=_get_document_type(template_id),
        is_system=False,
        created_by=current_user.id,
        fields=system_template.get("fields", {}),
        sections=system_template.get("sections", []),
        sample_data=_generate_sample_data(system_template),
        is_active=True,
        is_public=False,
        tags=system_template.get("tags", []) + ["custom", "user-created"],
    )

    # Store the content template in a separate field or file
    # For now, we'll include it in the fields
    content = get_template_content(template_id)
    if content:
        user_template.fields["_content_template"] = content

    db.add(user_template)
    await db.commit()
    await db.refresh(user_template)

    return {
        "success": True,
        "message": f"Template copied successfully",
        "user_template": {
            "id": user_template.id,
            "key": user_template.template_key,
            "name": user_template.name,
            "description": user_template.description,
            "category": user_template.category,
            "created_at": user_template.created_at.isoformat() if user_template.created_at else None,
        }
    }


@router.get("/user/templates")
async def list_user_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all templates created/owned by the current user.
    """
    result = await db.execute(
        select(Template).where(
            Template.created_by == current_user.id,
            Template.is_active == True
        ).order_by(Template.created_at.desc())
    )
    templates = result.scalars().all()

    return {
        "count": len(templates),
        "templates": [
            {
                "id": t.id,
                "key": t.template_key,
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "document_type": t.document_type,
                "version": t.version,
                "tags": t.tags or [],
                "use_count": t.use_count,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in templates
        ]
    }


@router.get("/user/templates/{template_id}")
async def get_user_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific user template.
    """
    result = await db.execute(
        select(Template).where(
            Template.id == template_id,
            Template.created_by == current_user.id
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(404, "Template not found or access denied")

    return {
        "id": template.id,
        "key": template.template_key,
        "name": template.name,
        "description": template.description,
        "category": template.category,
        "document_type": template.document_type,
        "version": template.version,
        "fields": template.fields,
        "sections": template.sections,
        "sample_data": template.sample_data,
        "tags": template.tags or [],
        "use_count": template.use_count,
        "content_template": template.fields.get("_content_template", ""),
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


from pydantic import BaseModel
from app.services.lma_clauses_service import lma_clauses_service


# =============================================================================
# LMA CLAUSES API ENDPOINTS
# =============================================================================

@router.get("/lma/all")
async def get_all_lma_clauses():
    """Get all LMA clauses with categories."""
    clauses = lma_clauses_service.get_all_clauses()
    categories = lma_clauses_service.get_categories()
    return {
        "count": len(clauses),
        "categories": categories,
        "clauses": [lma_clauses_service.get_clause_summary(c["id"]) for c in clauses],
    }


@router.get("/lma/categories")
async def get_lma_categories():
    """Get all LMA clause categories."""
    return lma_clauses_service.get_categories()


@router.get("/lma/mandatory")
async def get_mandatory_lma_clauses():
    """Get all mandatory LMA clauses."""
    clauses = lma_clauses_service.get_mandatory_clauses()
    return {
        "count": len(clauses),
        "clauses": clauses,
    }


@router.get("/lma/exclusions")
async def get_lma_exclusions():
    """Get all LMA exclusion clauses."""
    exclusions = lma_clauses_service.get_exclusions()
    return {
        "count": len(exclusions),
        "clauses": exclusions,
    }


@router.get("/lma/search")
async def search_lma_clauses(q: str):
    """Search LMA clauses by name or description."""
    clauses = lma_clauses_service.search_clauses(q)
    return {
        "query": q,
        "count": len(clauses),
        "clauses": clauses,
    }


@router.get("/lma/category/{category}")
async def get_lma_clauses_by_category(category: str):
    """Get LMA clauses by category."""
    clauses = lma_clauses_service.get_clauses_by_category(category)
    return {
        "category": category,
        "count": len(clauses),
        "clauses": clauses,
    }


@router.get("/lma/clause/{clause_id}")
async def get_lma_clause(clause_id: str):
    """Get a specific LMA clause with full text."""
    clause = lma_clauses_service.get_clause_by_id(clause_id)
    if not clause:
        raise HTTPException(404, f"LMA clause '{clause_id}' not found")
    return clause


class LMARecommendRequest(BaseModel):
    risk_category: str
    territory: Optional[str] = None
    perils: Optional[List[str]] = None
    sum_insured: Optional[float] = None
    special_features: Optional[List[str]] = None


@router.post("/lma/recommend")
async def recommend_lma_clauses(request: LMARecommendRequest):
    """
    Get LMA clause recommendations based on risk profile.

    Returns mandatory, recommended, and optional clauses.
    """
    recommendations = lma_clauses_service.recommend_clauses(
        risk_category=request.risk_category,
        territory=request.territory,
        perils=request.perils,
        sum_insured=request.sum_insured,
        special_features=request.special_features,
    )
    return {
        "risk_category": request.risk_category,
        "territory": request.territory,
        "mandatory": recommendations["mandatory"],
        "mandatory_count": len(recommendations["mandatory"]),
        "recommended": recommendations["recommended"],
        "recommended_count": len(recommendations["recommended"]),
        "optional": recommendations["optional"],
        "optional_count": len(recommendations["optional"]),
    }


class PricingImpactRequest(BaseModel):
    base_premium: float
    selected_clauses: List[str]


@router.post("/lma/pricing-impact")
async def calculate_lma_pricing_impact(request: PricingImpactRequest):
    """
    Calculate premium impact based on selected LMA clauses.

    Returns detailed breakdown of how each clause affects the premium.
    """
    impact = lma_clauses_service.calculate_pricing_impact(
        base_premium=request.base_premium,
        selected_clauses=request.selected_clauses,
    )
    return impact


@router.post("/lma/recommend/{assessment_id}")
async def recommend_lma_for_assessment(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get LMA clause recommendations for a specific assessment.

    Analyzes the assessment's risk profile and recommends appropriate clauses.
    """
    from app.models.assessment import Assessment

    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Extract risk profile from assessment
    risk_category = assessment.risk_category.value if assessment.risk_category else "property"
    territory = assessment.territory
    perils = []
    special_features = []

    # Extract perils from exposure details
    if assessment.exposure_details:
        perils = assessment.exposure_details.get("perils", [])
        special_features = assessment.exposure_details.get("special_features", [])

    recommendations = lma_clauses_service.recommend_clauses(
        risk_category=risk_category,
        territory=territory,
        perils=perils,
        sum_insured=assessment.sum_insured,
        special_features=special_features,
    )

    # Calculate pricing if premium is available
    pricing = None
    if assessment.premium:
        all_selected = [c["id"] for c in recommendations["mandatory"]] + \
                       [c["id"] for c in recommendations["recommended"]]
        pricing = lma_clauses_service.calculate_pricing_impact(
            base_premium=assessment.premium,
            selected_clauses=all_selected,
        )

    return {
        "assessment_id": assessment_id,
        "assessment_reference": assessment.reference_number,
        "risk_category": risk_category,
        "territory": territory,
        "mandatory": recommendations["mandatory"],
        "recommended": recommendations["recommended"],
        "optional": recommendations["optional"],
        "pricing": pricing,
    }


# =============================================================================
# TEMPLATE UPDATE ENDPOINTS
# =============================================================================

class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content_template: Optional[str] = None
    fields: Optional[dict] = None

@router.put("/user/templates/{template_id}")
async def update_user_template(
    template_id: int,
    update_data: TemplateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a user's custom template.
    """
    result = await db.execute(
        select(Template).where(
            Template.id == template_id,
            Template.created_by == current_user.id
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(404, "Template not found or access denied")

    if update_data.name:
        template.name = update_data.name
    if update_data.description:
        template.description = update_data.description
    if update_data.content_template:
        if template.fields is None:
            template.fields = {}
        template.fields["_content_template"] = update_data.content_template
    if update_data.fields:
        for key, value in update_data.fields.items():
            if key != "_content_template":
                template.fields[key] = value

    await db.commit()
    await db.refresh(template)

    return {
        "success": True,
        "message": "Template updated successfully",
        "template": {
            "id": template.id,
            "name": template.name,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        }
    }


@router.delete("/user/templates/{template_id}")
async def delete_user_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a user's custom template (soft delete).
    """
    result = await db.execute(
        select(Template).where(
            Template.id == template_id,
            Template.created_by == current_user.id
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(404, "Template not found or access denied")

    template.is_active = False
    await db.commit()

    return {
        "success": True,
        "message": "Template deleted successfully"
    }


@router.get("/{template_id}/fields")
async def get_template_fields(template_id: str):
    """
    Get just the field definitions for a template.
    Useful for building dynamic forms.
    """
    template = get_template(template_id)

    if not template:
        raise HTTPException(404, f"Template '{template_id}' not found")

    return {
        "template_id": template_id,
        "template_name": template["name"],
        "fields": template.get("fields", {})
    }


def _generate_sample_data(template: dict) -> dict:
    """Generate sample data for template preview."""

    samples = {
        # Risk Details
        "umr": "B0712ABCDEF123",
        "broker_ref": "AON/2026/001234",
        "unique_market_reference": "B0712ABCDEF123",
        "placing_broker_contract_ref": "AON/2026/001234",
        "type_of_business": "New",
        "placing_type": "Open Market",
        "risk_code": "PC",
        "class_of_business": "Commercial Property All Risks",

        # Assured/Insured
        "insured_name": "Acme Corporation Ltd",
        "insured_address": "123 Business Park, London EC2A 1AB, United Kingdom",
        "insured_country": "United Kingdom",
        "named_insured": "Acme Corporation Ltd",
        "firm_name": "Smith & Associates LLP",
        "firm_address": "456 Professional House, Manchester M1 2AB",
        "assured_name": "Global Trading Co Ltd",
        "assured_address": "789 Export Centre, Southampton SO14 3FE",

        # Broker
        "broker_name": "Aon Risk Solutions",
        "broker_address": "The Leadenhall Building, 122 Leadenhall Street, London EC3V 4AB",
        "broker_reference": "AON-2026-001234",
        "broker_pin": "A1234",

        # Policy Details
        "policy_number": "POL-2026-001234",
        "certificate_number": "CERT-2026-001234",
        "cover_note_number": "CN-2026-001234",

        # Period
        "period_from": datetime.now().strftime("%d %B %Y"),
        "period_to": (datetime.now() + timedelta(days=365)).strftime("%d %B %Y"),
        "inception_time": "00:01",
        "retroactive_date": "Unlimited",
        "issue_date": datetime.now().strftime("%d %B %Y"),
        "valid_until": (datetime.now() + timedelta(days=30)).strftime("%d %B %Y"),

        # Coverage
        "interest": "All Risks of Physical Loss or Damage to Property including but not limited to:\n- Buildings and Contents\n- Plant and Machinery\n- Stock and Materials\n- Business Interruption",
        "territorial_limits": "Worldwide excluding USA/Canada",
        "basis_of_cover": "Occurrence",

        # Financial
        "limit_of_liability": "GBP 10,000,000",
        "aggregate_limit": "GBP 20,000,000",
        "limit_any_one_claim": "GBP 5,000,000",
        "premium_amount": "GBP 125,000",
        "premium": "GBP 125,000",
        "deductible": "GBP 50,000",
        "excess": "GBP 25,000",
        "currency": "GBP",
        "premium_terms": "Annual premium payable in full upon inception",
        "sub_limits": "Terrorism: GBP 5,000,000 any one occurrence\nFlood: GBP 2,500,000 any one occurrence",
        "sum_insured": "USD 500,000",

        # Security
        "lead_underwriter": "J. Smith",
        "lead_syndicate": "Syndicate 1234",
        "lead_reference": "SYN1234/2026/00123",
        "signed_line": "100",
        "order_percentage": "25",
        "following_markets": "Syndicate 2345 - 15%\nSyndicate 3456 - 10%\nSyndicate 4567 - 10%",
        "security_details": "Syndicate 1234 - 25%\nSyndicate 2345 - 25%\nSyndicate 3456 - 25%\nSyndicate 4567 - 25%",

        # Conditions
        "subjectivities": "1. Receipt of completed proposal form\n2. Satisfactory survey report\n3. No material change in risk",
        "warranties": "1. Fire extinguishers maintained annually\n2. Intruder alarm in operation\n3. Professional qualifications maintained",
        "exclusions": "1. Gradual deterioration\n2. Cyber events (unless specifically included)\n3. Asbestos",
        "conditions": "1. Premium payment within 30 days of inception\n2. Claims notification within 7 days",
        "special_conditions": "Survey to be completed within 60 days of inception",

        # Claims
        "claims_contact": "Lloyd's Claims Office",
        "claims_location": "London",
        "claims_handler": "XYZ Claims Services Ltd",
        "claims_address": "Claims House, 100 Minories, London EC3N 1BN",
        "claims_email": "claims@xyzservices.com",

        # Coverage Parts
        "coverage_a_title": "Professional Liability",
        "coverage_a_text": "The Underwriters will pay on behalf of the Insured all sums which the Insured shall become legally obligated to pay as damages by reason of any negligent act, error or omission in the performance of professional services.",
        "coverage_b_title": "Defence Costs",
        "coverage_b_text": "The Underwriters will pay Defence Costs incurred in the investigation, defence, appeal or settlement of any Claim.",
        "defence_costs_treatment": "Inside Limit",

        # Professional Indemnity specific
        "profession": "Consulting Engineers",
        "loss_of_documents_limit": "GBP 250,000",
        "court_attendance_rate": "GBP 500",

        # Marine specific
        "cargo_description": "Electronic Components and Computer Equipment\nHS Code: 8471.30\nValue: USD 500,000",
        "marks_numbers": "ACME/2026/001-050",
        "packing_type": "Containerized (FCL)",
        "from_location": "Shanghai, China",
        "to_location": "Southampton, United Kingdom",
        "via_location": "Singapore",
        "conveyance_type": "Sea",
        "vessel_name": "MV Ocean Carrier",
        "interest_type": "Buyer/Importer",
        "valuation_basis": "CIF + 10%",

        # Certificate of Insurance specific
        "producer_name": "ABC Insurance Brokers Ltd",
        "producer_address": "100 Broker Street, London EC3M 1AA",
        "producer_contact": "John Broker",
        "producer_phone": "+44 20 1234 5678",
        "producer_email": "jbroker@abcbrokers.com",
        "certificate_holder_name": "Mega Construction Ltd",
        "certificate_holder_address": "Construction House, Birmingham B1 1AA",
        "description_of_operations": "General contracting and construction services for commercial buildings",
        "additional_insured": "Yes",
        "subrogation_waived": "Yes",
        "issuer_name": "ABC Insurance Brokers Ltd",

        # GL specific
        "gl_policy_number": "GL-2026-001234",
        "gl_insurer": "Lloyd's Syndicate 1234",
        "gl_effective_date": datetime.now().strftime("%d %B %Y"),
        "gl_expiration_date": (datetime.now() + timedelta(days=365)).strftime("%d %B %Y"),
        "gl_each_occurrence": "GBP 2,000,000",
        "gl_general_aggregate": "GBP 5,000,000",
        "gl_products_completed": "GBP 2,000,000",
        "gl_personal_adv_injury": "GBP 1,000,000",

        # Auto specific
        "auto_policy_number": "AUTO-2026-001234",
        "auto_insurer": "Lloyd's Syndicate 2345",
        "auto_effective_date": datetime.now().strftime("%d %B %Y"),
        "auto_expiration_date": (datetime.now() + timedelta(days=365)).strftime("%d %B %Y"),
        "auto_combined_single": "GBP 5,000,000",

        # Umbrella specific
        "umbrella_policy_number": "UMB-2026-001234",
        "umbrella_insurer": "Lloyd's Syndicate 3456",
        "umbrella_effective_date": datetime.now().strftime("%d %B %Y"),
        "umbrella_expiration_date": (datetime.now() + timedelta(days=365)).strftime("%d %B %Y"),
        "umbrella_each_occurrence": "GBP 10,000,000",
        "umbrella_aggregate": "GBP 10,000,000",

        # WC specific
        "wc_policy_number": "WC-2026-001234",
        "wc_insurer": "Lloyd's Syndicate 4567",
        "wc_effective_date": datetime.now().strftime("%d %B %Y"),
        "wc_expiration_date": (datetime.now() + timedelta(days=365)).strftime("%d %B %Y"),
        "wc_el_each_accident": "GBP 10,000,000",
        "wc_el_disease_policy": "GBP 10,000,000",

        # Additional info
        "additional_information": "This placing slip is subject to Lloyd's minimum standards.",
    }

    return samples


def _get_document_type(template_id: str) -> str:
    """Map template ID to document type."""
    type_map = {
        "lloyds_mrc_slip": "slip",
        "lloyds_policy_wording": "policy",
        "lloyds_cover_note": "certificate",
        "certificate_of_insurance": "certificate",
        "marine_cargo": "policy",
        "professional_indemnity": "policy",
    }
    return type_map.get(template_id, "other")


# =============================================================================
# DOCUMENT LIBRARY API - 20GB Knowledge Base
# =============================================================================

import os
from pathlib import Path

DATA_DIR = Path("/app/app/data")
INSURANCE_DATA_DIR = DATA_DIR / "insurance_data"
TRAINING_DATA_DIR = DATA_DIR / "training_data"


def _get_dir_stats(path: Path) -> dict:
    """Get document count and size for a directory."""
    if not path.exists():
        return {"count": 0, "size_mb": 0}

    count = 0
    size = 0
    for f in path.rglob("*"):
        if f.is_file():
            count += 1
            size += f.stat().st_size

    return {"count": count, "size_mb": round(size / (1024 * 1024), 2)}


@router.get("/library/categories")
async def get_document_library():
    """
    Get all document categories from the 20GB knowledge base.
    Returns categories with document counts, sizes, and metadata.
    """
    categories = []

    # Insurance Data Categories (18GB)
    insurance_categories = [
        ("actuarial", "Actuarial Models", "pricing", "Actuarial tables, loss models, and pricing algorithms"),
        ("auto", "Auto Insurance", "automobile", "Motor vehicle policies, claims data, and underwriting guides"),
        ("catastrophe", "Catastrophe Models", "disaster", "CAT models, exposure data, and reinsurance structures"),
        ("claims", "Claims Data", "legal_document", "Claims histories, reserves, and settlement patterns"),
        ("clauses", "Policy Clauses", "clause", "Standard and specialty policy clause libraries"),
        ("contract_clauses", "Contract Clauses", "contract", "Legal contract clauses and provisions"),
        ("fraud", "Fraud Detection", "security", "Fraud indicators, patterns, and detection models"),
        ("global", "Global Markets", "world", "International insurance markets and regulations"),
        ("health", "Health Insurance", "medical", "Medical underwriting, claims, and compliance"),
        ("legal_cases", "Legal Cases", "gavel", "Court decisions, precedents, and case law"),
        ("lloyds_public", "Lloyd's Market", "lloyds", "Lloyd's market data, syndicates, and practices"),
        ("lma", "LMA Clauses", "verified", "Lloyd's Market Association official clauses"),
        ("open_source", "Open Source Data", "database", "Public insurance datasets and research"),
        ("policies", "Policy Wordings", "policy", "Full policy documents and wordings"),
        ("pricing", "Pricing Models", "calculator", "Premium calculation and rating models"),
    ]

    for folder, name, icon, desc in insurance_categories:
        path = INSURANCE_DATA_DIR / folder
        stats = _get_dir_stats(path)
        if stats["count"] > 0:
            categories.append({
                "id": folder,
                "name": name,
                "icon": icon,
                "description": desc,
                "type": "insurance",
                "document_count": stats["count"],
                "size_mb": stats["size_mb"],
                "path": str(path),
            })

    # Training Data Categories (1.4GB)
    training_categories = [
        ("atticus", "Atticus Legal", "legal", "Legal document analysis datasets"),
        ("australian_legal", "Australian Legal", "aus", "Australian legal documents and precedents"),
        ("case_hold", "Case Holdings", "judge", "Legal case holdings and decisions"),
        ("chat_finetune", "Chat Training", "chat", "78K+ Q&A pairs for AI training"),
        ("contract_nli", "Contract NLI", "inference", "Natural language inference for contracts"),
        ("cuad", "CUAD Dataset", "contracts", "Contract understanding benchmark data"),
        ("echr", "ECHR Cases", "europe", "European Court of Human Rights decisions"),
        ("echr_b", "ECHR Benchmark", "benchmark", "ECHR classification benchmark"),
        ("eurlex", "EUR-Lex", "eu", "European Union legal documents"),
        ("full_policies", "Full Policies", "document", "Complete policy document examples"),
        ("law_stack_exchange", "Law Q&A", "qa", "Legal Q&A from Stack Exchange"),
        ("ledgar", "LEDGAR Contracts", "ledgar", "SEC contract provisions dataset"),
        ("legalbench", "Legal Benchmark", "test", "Legal reasoning benchmark tasks"),
        ("legal_contracts", "Legal Contracts", "contract_alt", "Contract clause classification"),
        ("maud", "M&A Dataset", "merger", "Merger and acquisition documents"),
    ]

    for folder, name, icon, desc in training_categories:
        path = TRAINING_DATA_DIR / folder
        stats = _get_dir_stats(path)
        if stats["count"] > 0:
            categories.append({
                "id": folder,
                "name": name,
                "icon": icon,
                "description": desc,
                "type": "training",
                "document_count": stats["count"],
                "size_mb": stats["size_mb"],
                "path": str(path),
            })

    # Calculate totals
    total_docs = sum(c["document_count"] for c in categories)
    total_size = sum(c["size_mb"] for c in categories)

    return {
        "total_documents": total_docs,
        "total_size_gb": round(total_size / 1024, 2),
        "insurance_categories": len([c for c in categories if c["type"] == "insurance"]),
        "training_categories": len([c for c in categories if c["type"] == "training"]),
        "categories": categories,
    }


@router.get("/library/category/{category_id}")
async def get_category_documents(
    category_id: str,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None
):
    """
    Get documents from a specific category.
    """
    # Check both directories
    path = INSURANCE_DATA_DIR / category_id
    if not path.exists():
        path = TRAINING_DATA_DIR / category_id
    if not path.exists():
        raise HTTPException(404, f"Category '{category_id}' not found")

    documents = []
    for f in path.rglob("*"):
        if f.is_file():
            # Skip if search doesn't match
            if search and search.lower() not in f.name.lower():
                continue

            stat = f.stat()
            documents.append({
                "id": str(f.relative_to(path)),
                "name": f.name,
                "path": str(f),
                "size_kb": round(stat.st_size / 1024, 2),
                "extension": f.suffix.lower(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    # Sort by modification time (newest first)
    documents.sort(key=lambda x: x["modified"], reverse=True)

    return {
        "category": category_id,
        "total": len(documents),
        "limit": limit,
        "offset": offset,
        "documents": documents[offset:offset + limit],
    }


@router.get("/library/document")
async def get_document_content(path: str, preview: bool = True):
    """
    Get content of a specific document.
    """
    file_path = Path(path)

    # Security check - must be within our data directories
    if not (str(file_path).startswith(str(DATA_DIR))):
        raise HTTPException(403, "Access denied")

    if not file_path.exists():
        raise HTTPException(404, "Document not found")

    try:
        # Read content based on file type
        if file_path.suffix.lower() in ['.json', '.jsonl']:
            with open(file_path, 'r') as f:
                if preview:
                    # Read first 10 lines for preview
                    lines = []
                    for i, line in enumerate(f):
                        if i >= 10:
                            break
                        lines.append(line)
                    content = "".join(lines)
                    if i >= 10:
                        content += "\n... (truncated)"
                else:
                    content = f.read()
        elif file_path.suffix.lower() in ['.txt', '.md', '.csv']:
            with open(file_path, 'r') as f:
                if preview:
                    content = f.read(10000)  # First 10KB
                    if len(content) >= 10000:
                        content += "\n... (truncated)"
                else:
                    content = f.read()
        else:
            content = f"Binary file: {file_path.name} ({file_path.stat().st_size / 1024:.1f} KB)"

        return {
            "path": str(file_path),
            "name": file_path.name,
            "size_kb": round(file_path.stat().st_size / 1024, 2),
            "content": content,
            "is_preview": preview,
        }
    except Exception as e:
        raise HTTPException(500, f"Error reading document: {str(e)}")
