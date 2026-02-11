"""Contract Generation Router - PDF generation for insurance contracts"""
import os
import json
import uuid
from datetime import datetime, timezone
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment

router = APIRouter()

# Contract templates
CONTRACT_TEMPLATES = {
    "property": {
        "name": "Property Insurance Policy",
        "description": "Standard property insurance policy for commercial and residential properties",
        "sections": ["Declarations", "Insuring Agreement", "Exclusions", "Conditions", "Definitions"]
    },
    "liability": {
        "name": "General Liability Policy",
        "description": "Comprehensive general liability insurance coverage",
        "sections": ["Coverage Agreement", "Who Is Insured", "Limits of Insurance", "Exclusions", "Conditions"]
    },
    "cyber": {
        "name": "Cyber Liability Policy",
        "description": "Coverage for cyber risks, data breaches, and network security",
        "sections": ["Insuring Agreements", "Definitions", "Exclusions", "Claims Conditions", "General Conditions"]
    },
    "marine": {
        "name": "Marine Cargo Policy",
        "description": "Coverage for goods in transit by sea, air, or land",
        "sections": ["Voyage Clause", "Perils Covered", "Exclusions", "Claims", "General Conditions"]
    },
    "professional": {
        "name": "Professional Indemnity Policy",
        "description": "Coverage for professional negligence and errors & omissions",
        "sections": ["Insuring Clause", "Extensions", "Exclusions", "Claims Conditions", "General Terms"]
    }
}

@router.get("/templates")
async def get_templates():
    """Get available contract templates."""
    return {
        "templates": [
            {"id": k, "name": v["name"], "description": v["description"]}
            for k, v in CONTRACT_TEMPLATES.items()
        ]
    }

@router.post("/generate/{assessment_id}")
async def generate_contract(
    assessment_id: str,
    template_id: str = "property",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a PDF contract for an assessment."""
    # Fetch assessment with owner verification
    result = await db.execute(select(Assessment).where(
        Assessment.id == assessment_id,
        Assessment.created_by == current_user.id
    ))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(404, "Assessment not found or access denied")

    if assessment.decision.value != "go":
        raise HTTPException(400, "Cannot generate contract for non-approved assessment")

    template = CONTRACT_TEMPLATES.get(template_id, CONTRACT_TEMPLATES["property"])

    # Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=HexColor('#1a365d')
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10,
        textColor=HexColor('#2d3748')
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        alignment=TA_JUSTIFY
    )

    story = []

    # Header
    story.append(Paragraph("INSURANCE POLICY", title_style))
    story.append(Paragraph(template["name"], heading_style))
    story.append(Spacer(1, 20))

    # Policy Details Table
    policy_data = [
        ["Policy Number:", assessment.reference_number or f"POL-{assessment.id:06d}"],
        ["Insured:", assessment.insured_name or "To Be Confirmed"],
        ["Risk Category:", assessment.risk_category.value.replace("_", " ").title() if assessment.risk_category else "Property"],
        ["Territory:", assessment.territory or "As Declared"],
        ["Sum Insured:", f"€{assessment.sum_insured:,.2f}" if assessment.sum_insured else "As Declared"],
        ["Premium:", f"€{assessment.premium:,.2f}" if assessment.premium else "As Quoted"],
        ["Deductible:", f"€{assessment.deductible:,.2f}" if assessment.deductible else "As Agreed"],
        ["Effective Date:", datetime.now().strftime("%d %B %Y")],
        ["Expiry Date:", (datetime.now().replace(year=datetime.now().year + 1)).strftime("%d %B %Y")],
    ]

    policy_table = Table(policy_data, colWidths=[4*cm, 10*cm])
    policy_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('LINEBELOW', (0, -1), (-1, -1), 1, HexColor('#e2e8f0')),
    ]))
    story.append(policy_table)
    story.append(Spacer(1, 30))

    # Contract Sections
    for section in template["sections"]:
        story.append(Paragraph(section.upper(), heading_style))

        # Generate placeholder content based on section
        if section == "Declarations" or section == "Coverage Agreement":
            content = f"""
            This policy is issued to the Named Insured shown above. In consideration of the premium paid,
            the Insurer agrees to provide the coverage described herein, subject to all terms, conditions,
            and limitations of this policy. The coverage applies to the risks described in the schedule
            and within the territorial limits specified.
            """
        elif section == "Insuring Agreement" or section == "Insuring Clause":
            content = f"""
            The Insurer will indemnify the Insured against all sums which the Insured shall become legally
            liable to pay as damages in respect of {assessment.risk_category.value if assessment.risk_category else 'insured'}
            losses occurring during the policy period. Coverage is subject to the limits, terms, and
            conditions stated herein.
            """
        elif section == "Exclusions":
            content = """
            This policy does not cover: (a) War, invasion, or acts of foreign enemies; (b) Nuclear reaction
            or contamination; (c) Intentional acts by the Insured; (d) Wear and tear or gradual deterioration;
            (e) Losses arising from illegal activities; (f) Pre-existing conditions known to the Insured
            at inception of this policy.
            """
        elif section == "Conditions" or section == "General Conditions":
            content = """
            The Insured shall: (a) Take reasonable precautions to prevent loss; (b) Notify the Insurer
            promptly of any claim or occurrence likely to give rise to a claim; (c) Cooperate fully with
            the Insurer in the investigation and defense of any claim; (d) Not admit liability without
            the Insurer's written consent.
            """
        else:
            content = f"""
            [Standard {section} provisions apply as per the Insurer's standard policy wording.
            Please refer to the full policy documentation for complete details.]
            """

        story.append(Paragraph(content, normal_style))
        story.append(Spacer(1, 15))

    # AI Analysis Summary (if available)
    if assessment.ai_analysis:
        story.append(Paragraph("AI RISK ASSESSMENT SUMMARY", heading_style))

        analysis = assessment.ai_analysis
        if isinstance(analysis, str):
            analysis = json.loads(analysis)

        summary = f"""
        This policy was underwritten with AI assistance. The risk assessment indicated a confidence
        score of {assessment.confidence_score}% with the following key findings:
        """
        story.append(Paragraph(summary, normal_style))

        if assessment.ai_recommendations:
            recs = assessment.ai_recommendations
            if isinstance(recs, str):
                recs = json.loads(recs)
            for rec in recs[:5]:
                story.append(Paragraph(f"• {rec}", normal_style))

        story.append(Spacer(1, 20))

    # Signature Block
    story.append(Spacer(1, 40))
    story.append(Paragraph("AUTHORIZED SIGNATURES", heading_style))

    sig_data = [
        ["_" * 30, "_" * 30],
        ["For and on behalf of the Insurer", "Insured / Authorized Representative"],
        ["", ""],
        ["Date: _________________", "Date: _________________"],
    ]

    sig_table = Table(sig_data, colWidths=[7*cm, 7*cm])
    sig_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(sig_table)

    # Footer
    story.append(Spacer(1, 30))
    footer = f"""
    <para align="center" fontSize="9" textColor="#718096">
    Generated by InstantRisk AI Underwriting Platform<br/>
    Reference: {assessment.reference_number or f'IR-{assessment.id:06d}'}<br/>
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
    </para>
    """
    story.append(Paragraph(footer, styles['Normal']))

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    filename = f"contract_{assessment.reference_number or assessment.id}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/{assessment_id}/preview")
async def preview_contract(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get contract preview data without generating PDF."""
    result = await db.execute(select(Assessment).where(
        Assessment.id == assessment_id,
        Assessment.created_by == current_user.id
    ))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(404, "Assessment not found or access denied")

    return {
        "assessment_id": assessment.id,
        "reference_number": assessment.reference_number,
        "insured_name": assessment.insured_name,
        "risk_category": assessment.risk_category.value if assessment.risk_category else None,
        "decision": assessment.decision.value if assessment.decision else None,
        "premium": assessment.premium,
        "sum_insured": assessment.sum_insured,
        "deductible": assessment.deductible,
        "territory": assessment.territory,
        "effective_date": datetime.now().isoformat(),
        "expiry_date": (datetime.now().replace(year=datetime.now().year + 1)).isoformat(),
        "templates": list(CONTRACT_TEMPLATES.keys())
    }
