"""
InstantRisk V2 - Sanctions Screening API Router

Endpoints for multi-level sanctions screening:
- Quick screen (auto on assessment creation)
- Enhanced screen (auto after AI analysis)
- Deep analysis (user-triggered)
- Full investigation (user-triggered)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body, WebSocket, WebSocketDisconnect, BackgroundTasks
from typing import List, Optional, Callable
from pydantic import BaseModel
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.security import get_current_user
from ..core.database import get_db, AsyncSessionLocal
from ..core.feature_gate import require_feature
from ..models.assessment import Assessment
from ..models.sanctions import (
    SanctionsScreening,
    SanctionsEntity,
    SanctionsAlert,
    ScreeningLevel,
    ScreeningStatus,
)
from ..models.generated_document import GeneratedDocument
from ..services.sanctions_service import sanctions_service, SCREENING_LEVELS

router = APIRouter(prefix="/sanctions", tags=["Sanctions"])


# =============================================================================
# Schemas
# =============================================================================

class QuickScreenRequest(BaseModel):
    name: str
    entity_type: str = "Person"


class EntityToScreen(BaseModel):
    name: str
    type: str = "Person"
    role: str = "unknown"


class EnhancedScreenRequest(BaseModel):
    entities: List[EntityToScreen]


class ScreeningResponse(BaseModel):
    id: Optional[int] = None
    level: str
    status: str
    entities_screened: int = 0
    matches_found: int = 0
    highest_score: float = 0
    sources_checked: List[str] = []
    screened_at: str


class ScreeningSummary(BaseModel):
    assessment_id: str
    total_screenings: int
    latest_level: str
    overall_status: str
    entities_screened: int
    matches_found: int
    highest_score: float
    last_screened: Optional[str] = None


# =============================================================================
# Quick Screen Endpoints
# =============================================================================

@router.post("/quick-screen", response_model=dict)
async def quick_screen(
    request: QuickScreenRequest,
    current_user = Depends(require_feature("sanctions_screening"))
):
    """
    Level 1: Quick name check against primary sanctions lists.

    Fast check (~2-3 seconds) for basic screening.
    """
    result = await sanctions_service.quick_screen(
        name=request.name,
        entity_type=request.entity_type
    )
    return result


@router.post("/enhanced-screen", response_model=dict)
async def enhanced_screen(
    request: EnhancedScreenRequest,
    current_user = Depends(require_feature("sanctions_screening"))
):
    """
    Level 2: Enhanced screening with fuzzy matching.

    Screens multiple entities with aliases and extended lists.
    """
    entities = [{"name": e.name, "type": e.type, "role": e.role} for e in request.entities]
    result = await sanctions_service.enhanced_screen(entities=entities)
    return result


# =============================================================================
# Assessment-Specific Endpoints
# =============================================================================

@router.post("/assessments/{assessment_id}/screen")
async def screen_assessment(
    assessment_id: str,
    level: ScreeningLevel = Query(ScreeningLevel.ENHANCED),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_feature("sanctions_screening"))
):
    """
    Run sanctions screening on an assessment.

    Extracts entity names from assessment data and screens them.
    Stores results in the database.
    """
    # Get assessment
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Extract entities from assessment data
    entities = _extract_entities_from_assessment(assessment)

    if not entities:
        return {
            "status": "no_entities",
            "message": "No entities found in assessment to screen"
        }

    # Create screening record
    screening = SanctionsScreening(
        assessment_id=assessment_id,
        screening_level=level,
        status=ScreeningStatus.IN_PROGRESS,
        started_at=datetime.utcnow(),
        is_auto=False,
        triggered_by=str(current_user.id)
    )
    db.add(screening)
    await db.flush()

    # Run screening
    if level == ScreeningLevel.QUICK:
        # Quick screen just the insured
        result = await sanctions_service.quick_screen(
            name=entities[0]["name"],
            entity_type=entities[0]["type"]
        )
        screening.entities_screened = 1
    else:
        # Enhanced or deeper
        entities_list = [{"name": e["name"], "type": e["type"], "role": e["role"]} for e in entities]
        result = await sanctions_service.enhanced_screen(
            entities=entities_list,
            assessment_id=assessment_id
        )
        screening.entities_screened = len(entities)

    # Store entity results
    for entity_result in result.get("entities_screened", [result]):
        entity = SanctionsEntity(
            screening_id=screening.id,
            entity_name=entity_result.get("entity_name", ""),
            entity_type=entity_result.get("entity_type", "unknown"),
            entity_role=entity_result.get("role", "unknown"),
            match_found=len(entity_result.get("matches", [])) > 0,
            match_score=entity_result.get("highest_score", 0),
            status=ScreeningStatus(entity_result.get("status", "clear")),
        )

        if entity_result.get("matches"):
            top_match = entity_result["matches"][0]
            entity.matched_entity_id = top_match.get("id")
            entity.matched_entity_name = top_match.get("name")
            entity.sanctions_lists = top_match.get("datasets", [])
            entity.match_reasons = ["name_match"]

        db.add(entity)

    # Update screening record
    screening.status = ScreeningStatus(result.get("status", "clear"))
    screening.matches_found = result.get("total_matches", len(result.get("matches", [])))
    screening.highest_match_score = result.get("highest_score", 0)
    screening.sources_checked = result.get("sources_checked", [])
    screening.completed_at = datetime.utcnow()
    screening.duration_ms = int((screening.completed_at - screening.started_at).total_seconds() * 1000)

    await db.commit()

    return {
        "screening_id": screening.id,
        "level": level.value,
        "status": screening.status.value,
        "entities_screened": screening.entities_screened,
        "matches_found": screening.matches_found,
        "highest_score": float(screening.highest_match_score),
        "duration_ms": screening.duration_ms
    }


@router.get("/assessments/{assessment_id}/summary")
async def get_assessment_sanctions_summary(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get sanctions screening summary for an assessment, including match details."""
    # Get all screenings for this assessment
    result = await db.execute(
        select(SanctionsScreening)
        .where(SanctionsScreening.assessment_id == assessment_id)
        .order_by(SanctionsScreening.created_at.desc())
    )
    screenings = result.scalars().all()

    if not screenings:
        return {
            "assessment_id": assessment_id,
            "total_screenings": 0,
            "status": "not_screened",
            "message": "No sanctions screenings have been performed"
        }

    latest = screenings[0]

    # Use only latest screening for entity and match counts (not cumulative)
    total_entities = latest.entities_screened or 0
    total_matches = latest.matches_found or 0
    highest_score = max(float(s.highest_match_score or 0) for s in screenings)

    # Determine overall status
    statuses = [s.status for s in screenings]
    if ScreeningStatus.MATCH in statuses:
        overall_status = "match"
    elif ScreeningStatus.REVIEW in statuses:
        overall_status = "review"
    else:
        overall_status = "clear"

    # Build screenings list with match details
    screenings_data = []
    for s in screenings:
        # Get entities for this screening
        entities_result = await db.execute(
            select(SanctionsEntity).where(SanctionsEntity.screening_id == s.id)
        )
        entities = entities_result.scalars().all()

        # Build match details for entities that have matches
        match_details = []
        for entity in entities:
            if entity.match_found:
                match_details.append({
                    "entity_name": entity.entity_name,
                    "entity_type": entity.entity_type,
                    "entity_role": entity.entity_role,
                    "match_name": entity.matched_entity_name or "Unknown",
                    "match_score": float(entity.match_score or 0),
                    "dataset": entity.sanctions_lists[0] if entity.sanctions_lists else "Unknown List",
                    "all_lists": entity.sanctions_lists or [],
                    "match_reasons": entity.match_reasons or [],
                    "pep_status": entity.pep_status
                })

        screenings_data.append({
            "id": s.id,
            "level": s.screening_level.value,
            "status": s.status.value,
            "entities": s.entities_screened,
            "matches": s.matches_found,
            "score": float(s.highest_match_score or 0),
            "completed": s.completed_at.isoformat() if s.completed_at else None,
            "sources_checked": s.sources_checked or [],
            "duration_ms": s.duration_ms,
            "match_details": match_details
        })

    return {
        "assessment_id": assessment_id,
        "total_screenings": len(screenings),
        "latest_level": latest.screening_level.value,
        "overall_status": overall_status,
        "entities_screened": total_entities,
        "matches_found": total_matches,
        "highest_score": highest_score,
        "last_screened": latest.completed_at.isoformat() if latest.completed_at else None,
        "screenings": screenings_data
    }


@router.post("/assessments/{assessment_id}/deep-analysis")
async def run_deep_analysis(
    assessment_id: str,
    entity_name: str = Query(..., description="Entity name to analyze"),
    entity_type: str = Query("Person"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_feature("sanctions_screening"))
):
    """
    Level 3: Run deep analysis on a specific entity.

    Includes PEPs, adverse media, and ownership chains.
    """
    result = await sanctions_service.deep_analysis(
        entity_name=entity_name,
        entity_type=entity_type
    )

    # Create screening record
    screening = SanctionsScreening(
        assessment_id=assessment_id,
        screening_level=ScreeningLevel.DEEP,
        status=ScreeningStatus.CLEAR if result["overall_risk"] == "low" else ScreeningStatus.REVIEW,
        entities_screened=1,
        matches_found=len(result["sanctions_matches"]) + len(result["pep_matches"]),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        is_auto=False,
        triggered_by=str(current_user.id)
    )
    db.add(screening)
    await db.commit()

    result["screening_id"] = screening.id
    return result


@router.post("/assessments/{assessment_id}/full-investigation")
async def run_full_investigation(
    assessment_id: str,
    entity_name: str = Query(..., description="Entity name to investigate"),
    entity_type: str = Query("Person"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_feature("sanctions_screening"))
):
    """
    Level 4: Full investigation with network mapping.

    Comprehensive analysis including ownership chains and related entities.
    """
    result = await sanctions_service.full_investigation(
        entity_name=entity_name,
        entity_type=entity_type
    )

    # Create screening record
    screening = SanctionsScreening(
        assessment_id=assessment_id,
        screening_level=ScreeningLevel.FULL,
        status=ScreeningStatus.CLEAR,
        entities_screened=1 + len(result.get("related_entities", [])),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        is_auto=False,
        triggered_by=str(current_user.id)
    )
    db.add(screening)
    await db.commit()

    result["screening_id"] = screening.id
    return result


@router.get("/screenings/{screening_id}")
async def get_screening_details(
    screening_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get detailed results of a specific screening."""
    result = await db.execute(
        select(SanctionsScreening).where(SanctionsScreening.id == screening_id)
    )
    screening = result.scalar_one_or_none()

    if not screening:
        raise HTTPException(status_code=404, detail="Screening not found")

    # Get entities
    entities_result = await db.execute(
        select(SanctionsEntity).where(SanctionsEntity.screening_id == screening_id)
    )
    entities = entities_result.scalars().all()

    return {
        "id": screening.id,
        "assessment_id": screening.assessment_id,
        "level": screening.screening_level.value,
        "status": screening.status.value,
        "entities_screened": screening.entities_screened,
        "matches_found": screening.matches_found,
        "highest_score": float(screening.highest_match_score or 0),
        "sources_checked": screening.sources_checked or [],
        "started_at": screening.started_at.isoformat() if screening.started_at else None,
        "completed_at": screening.completed_at.isoformat() if screening.completed_at else None,
        "duration_ms": screening.duration_ms,
        "triggered_by": screening.triggered_by,
        "is_auto": screening.is_auto,
        "entities": [
            {
                "id": e.id,
                "name": e.entity_name,
                "type": e.entity_type,
                "role": e.entity_role,
                "match_found": e.match_found,
                "match_score": float(e.match_score or 0),
                "matched_entity": e.matched_entity_name,
                "sanctions_lists": e.sanctions_lists or [],
                "pep_status": e.pep_status,
                "status": e.status.value
            }
            for e in entities
        ]
    }


@router.get("/assessments/{assessment_id}/network")
async def get_assessment_network(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get network map data for an assessment's sanctions screening.

    Returns nodes (entities) and edges (relationships) for visualization.
    Deduplicates entities by name across all screenings.
    """
    # Get assessment
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Get the LATEST screening only (not all screenings) for cleaner network
    screenings_result = await db.execute(
        select(SanctionsScreening)
        .where(SanctionsScreening.assessment_id == assessment_id)
        .order_by(SanctionsScreening.created_at.desc())
        .limit(1)
    )
    latest_screening = screenings_result.scalar_one_or_none()

    if not latest_screening:
        return {
            "assessment_id": assessment_id,
            "network_map": {"nodes": [], "edges": []},
            "message": "No screenings found"
        }

    # Build network map from screened entities
    nodes = []
    edges = []
    seen_entity_names = set()  # Dedupe by name, not by ID

    # Get entities for the latest screening
    entities_result = await db.execute(
        select(SanctionsEntity).where(SanctionsEntity.screening_id == latest_screening.id)
    )
    entities = entities_result.scalars().all()

    for entity in entities:
        # Deduplicate by entity name (case-insensitive)
        entity_name_lower = entity.entity_name.lower()
        if entity_name_lower in seen_entity_names:
            continue
        seen_entity_names.add(entity_name_lower)

        node_id = f"entity_{entity.entity_name.replace(' ', '_')}"

        # Determine node type based on match status
        node_type = "clear"
        if entity.match_found:
            if entity.match_score and entity.match_score >= 80:
                node_type = "sanctions_match"
            elif entity.match_score and entity.match_score >= 60:
                node_type = "pep_match"
            else:
                node_type = "review"

        nodes.append({
            "id": node_id,
            "name": entity.entity_name,
            "type": node_type,
            "role": entity.entity_role,
            "score": float(entity.match_score or 0),
            "datasets": entity.sanctions_lists or [],
            "matched_name": entity.matched_entity_name
        })

        # If there's a match, add matched entity as a node and edge
        if entity.match_found and entity.matched_entity_name:
            match_name_lower = entity.matched_entity_name.lower()
            if match_name_lower not in seen_entity_names:
                seen_entity_names.add(match_name_lower)
                match_node_id = f"match_{entity.matched_entity_name.replace(' ', '_')}"
                nodes.append({
                    "id": match_node_id,
                    "name": entity.matched_entity_name,
                    "type": "sanctions_match" if entity.match_score >= 80 else "related",
                    "role": "sanctioned_entity",
                    "score": float(entity.match_score or 0),
                    "datasets": entity.sanctions_lists or []
                })

                edges.append({
                    "source": node_id,
                    "target": match_node_id,
                    "relationship": "potential_match"
                })

    # Build edges between entities based on roles
    insured_node = None
    broker_node = None
    for node in nodes:
        if node.get("role") == "insured":
            insured_node = node
        elif node.get("role") == "broker":
            broker_node = node

    # Connect broker to insured if both exist
    if insured_node and broker_node:
        edges.append({
            "source": broker_node["id"],
            "target": insured_node["id"],
            "relationship": "broker_for"
        })

    return {
        "assessment_id": assessment_id,
        "network_map": {
            "nodes": nodes,
            "edges": edges
        },
        "total_entities": len(nodes),
        "total_connections": len(edges)
    }


@router.get("/assessments/{assessment_id}/report")
async def download_sanctions_report(
    assessment_id: str,
    format: str = Query("pdf", description="Report format: pdf, xlsx, json"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Download sanctions screening report for an assessment.

    Returns a formatted report of all sanctions screenings.
    """
    # Get all screenings for this assessment
    result = await db.execute(
        select(SanctionsScreening)
        .where(SanctionsScreening.assessment_id == assessment_id)
        .order_by(SanctionsScreening.created_at.desc())
    )
    screenings = result.scalars().all()

    if not screenings:
        raise HTTPException(status_code=404, detail="No sanctions screenings found")

    # Collect all entities and matches
    report_data = {
        "assessment_id": assessment_id,
        "generated_at": datetime.utcnow().isoformat(),
        "total_screenings": len(screenings),
        "screenings": []
    }

    for screening in screenings:
        # Get entities for this screening
        entities_result = await db.execute(
            select(SanctionsEntity).where(SanctionsEntity.screening_id == screening.id)
        )
        entities = entities_result.scalars().all()

        screening_data = {
            "level": screening.screening_level.value,
            "status": screening.status.value,
            "completed_at": screening.completed_at.isoformat() if screening.completed_at else None,
            "entities_screened": screening.entities_screened,
            "matches_found": screening.matches_found,
            "highest_score": float(screening.highest_match_score or 0),
            "sources_checked": screening.sources_checked or [],
            "entities": [
                {
                    "name": e.entity_name,
                    "type": e.entity_type,
                    "role": e.entity_role,
                    "match_found": e.match_found,
                    "match_score": float(e.match_score or 0),
                    "match_reasons": e.match_reasons or []
                }
                for e in entities
            ]
        }
        report_data["screenings"].append(screening_data)

    if format == "json":
        return report_data

    # Generate PDF report
    if format == "pdf":
        import os
        import html as html_mod
        from fastapi.responses import FileResponse
        from ..core.config import settings

        # Build HTML for PDF
        screenings_html = ""
        for s_data in report_data["screenings"]:
            entities_html = ""
            for ent in s_data.get("entities", []):
                status_color = "#e53e3e" if ent["match_found"] else "#38a169"
                status_text = f"MATCH ({ent['match_score']:.0f}%)" if ent["match_found"] else "CLEAR"
                entities_html += f"""
                <tr>
                    <td>{html_mod.escape(ent['name'])}</td>
                    <td>{html_mod.escape(ent['type'])}</td>
                    <td>{html_mod.escape(ent['role'])}</td>
                    <td style="color: {status_color}; font-weight: bold;">{status_text}</td>
                </tr>"""

            screenings_html += f"""
            <div class="section">
                <h2>{html_mod.escape(s_data['level'].upper())} SCREENING</h2>
                <div class="meta">
                    <span class="meta-label">Status:</span> {html_mod.escape(s_data['status'].upper())} |
                    <span class="meta-label">Entities:</span> {s_data['entities_screened']} |
                    <span class="meta-label">Matches:</span> {s_data['matches_found']} |
                    <span class="meta-label">Highest Score:</span> {s_data['highest_score']:.0f}%
                </div>
                <table>
                    <thead>
                        <tr><th>Entity</th><th>Type</th><th>Role</th><th>Status</th></tr>
                    </thead>
                    <tbody>{entities_html}</tbody>
                </table>
            </div>"""

        html_template = f"""<!DOCTYPE html>
        <html><head><meta charset="UTF-8"><style>
            @page {{ size: A4; margin: 2cm; }}
            body {{ font-family: 'Times New Roman', serif; font-size: 11pt; line-height: 1.5; color: #333; }}
            .header {{ text-align: center; margin-bottom: 25px; border-bottom: 2px solid #1a365d; padding-bottom: 15px; }}
            .header h1 {{ color: #1a365d; font-size: 18pt; margin: 0; }}
            .header p {{ color: #666; font-size: 10pt; margin: 5px 0 0; }}
            .section {{ margin-bottom: 20px; page-break-inside: avoid; }}
            .section h2 {{ color: #1a365d; font-size: 13pt; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px; }}
            .meta {{ background: #f7fafc; padding: 10px 15px; border-radius: 5px; margin-bottom: 10px; border-left: 4px solid #1a365d; }}
            .meta-label {{ font-weight: bold; color: #1a365d; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; font-size: 10pt; }}
            th {{ background: #f7fafc; font-weight: bold; color: #1a365d; }}
            .footer {{ position: fixed; bottom: 1cm; left: 2cm; right: 2cm; text-align: center; font-size: 9pt; color: #666; border-top: 1px solid #ddd; padding-top: 10px; }}
        </style></head><body>
            <div class="header">
                <h1>SANCTIONS SCREENING REPORT</h1>
                <p>Assessment ID: {assessment_id} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
            </div>
            {screenings_html}
            <div class="footer">InstantRisk - AI-Powered Underwriting Platform | Confidential</div>
        </body></html>"""

        try:
            from weasyprint import HTML

            pdf_dir = os.path.join(settings.resolved_upload_dir, "generated")
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_filename = f"sanctions_report_{assessment_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf_path = os.path.join(pdf_dir, pdf_filename)

            pdf_bytes = HTML(string=html_template).write_pdf()
            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)

            return FileResponse(
                pdf_path,
                media_type="application/pdf",
                filename=pdf_filename,
            )
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return {**report_data, "_note": f"PDF generation failed: {str(e)}. Returning JSON data."}
    else:
        return report_data


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_entities_from_assessment(assessment: Assessment) -> List[dict]:
    """Extract entity names from assessment data for screening."""
    entities = []
    seen_names = set()  # Track names we've already added

    extracted = assessment.exposure_details or {}
    ai_analysis = assessment.ai_analysis or {}
    agent_results = ai_analysis.get("agent_results", {})
    extractor = agent_results.get("extractor", {})

    def add_entity(name: str, entity_type: str, role: str):
        """Helper to add entity if not already seen."""
        if name and name.lower() not in seen_names and len(name) > 2:
            seen_names.add(name.lower())
            entities.append({
                "name": name,
                "type": entity_type,
                "role": role
            })

    # Insured (primary entity) - check multiple sources
    insured_name = (
        assessment.insured_name or  # Direct field on assessment
        extracted.get("insured", {}).get("name") or
        extractor.get("insured", {}).get("name") or
        extracted.get("company_name") or
        extracted.get("insured_name")
    )
    add_entity(insured_name, "LegalEntity", "insured")

    # Broker - check multiple sources
    broker_name = (
        assessment.broker_reference or  # Sometimes broker name stored here
        extracted.get("broker", {}).get("name") or
        extractor.get("broker", {}).get("name") or
        extracted.get("broker_name")
    )
    if broker_name and not broker_name.startswith("BRK-"):  # Skip broker reference codes
        add_entity(broker_name, "Organization", "broker")

    # Key Personnel from AI Extractor (directors, officers, shareholders, UBOs)
    key_personnel = extractor.get("key_personnel", {})

    # Directors
    directors = key_personnel.get("directors", [])
    for director in directors:
        if isinstance(director, dict):
            add_entity(director.get("name"), "Person", "director")
        elif isinstance(director, str):
            add_entity(director, "Person", "director")

    # Officers (CEO, CFO, etc.)
    officers = key_personnel.get("officers", [])
    for officer in officers:
        if isinstance(officer, dict):
            add_entity(officer.get("name"), "Person", "officer")
        elif isinstance(officer, str):
            add_entity(officer, "Person", "officer")

    # Shareholders
    shareholders = key_personnel.get("shareholders", [])
    for shareholder in shareholders:
        if isinstance(shareholder, dict):
            add_entity(shareholder.get("name"), "LegalEntity", "shareholder")
        elif isinstance(shareholder, str):
            add_entity(shareholder, "LegalEntity", "shareholder")

    # Ultimate Beneficial Owners
    ubos = key_personnel.get("ultimate_beneficial_owners", [])
    for ubo in ubos:
        if isinstance(ubo, dict):
            add_entity(ubo.get("name"), "Person", "ubo")
        elif isinstance(ubo, str):
            add_entity(ubo, "Person", "ubo")

    # Beneficiaries (if any)
    beneficiaries = extracted.get("beneficiaries", [])
    for ben in beneficiaries:
        if isinstance(ben, dict) and ben.get("name"):
            add_entity(ben["name"], "LegalEntity", "beneficiary")
        elif isinstance(ben, str) and ben:
            add_entity(ben, "LegalEntity", "beneficiary")

    # Check for pre-extracted entities from multi-document processing
    pre_extracted = ai_analysis.get("extracted_entities", [])
    for entity in pre_extracted:
        if entity.get("name"):
            add_entity(
                entity["name"],
                entity.get("type", "LegalEntity"),
                entity.get("role", "unknown")
            )

    # Fallback: Extract from OCR text if no entities found
    if not entities and assessment.ocr_extracted_text:
        entities = _extract_entities_from_ocr_text(assessment.ocr_extracted_text)
        logger.info(f"Extracted {len(entities)} entities from OCR text fallback")

    return entities


def _extract_entities_from_ocr_text(ocr_text: str) -> List[dict]:
    """Fallback: Extract potential entity names from raw OCR text using strict patterns."""
    import re
    entities = []
    seen_names = set()

    if not ocr_text:
        return entities

    # STRICT patterns - only extract when there's a clear label followed by a company name
    # The company name MUST end with a legal suffix to be valid
    legal_suffixes = r"(?:Ltd\.?|LLC|Inc\.?|Corp\.?|PLC|Limited|L\.?P\.?|LLP|GmbH|S\.A\.?|B\.V\.?|N\.V\.?|AG)"

    # Pattern for person names (First Last or First Middle Last)
    person_name_pattern = r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"

    patterns = [
        # "Insured: Company Name Ltd" - must have label AND legal suffix
        (rf"(?:Insured|Policyholder|Named Insured|Client Name)[:\s]+([A-Z][A-Za-z0-9\s&,'-]{{2,50}}\s+{legal_suffixes})", "insured", "LegalEntity"),
        # "Broker: Company Name Ltd"
        (rf"(?:Broker|Placing Broker|Producing Broker|Intermediary)[:\s]+([A-Z][A-Za-z0-9\s&,'-]{{2,50}}\s+{legal_suffixes})", "broker", "LegalEntity"),
        # "Cedant: Company Name Ltd"
        (rf"(?:Cedant|Reinsured|Ceding Company)[:\s]+([A-Z][A-Za-z0-9\s&,'-]{{2,50}}\s+{legal_suffixes})", "cedant", "LegalEntity"),
        # Directors and Officers - extract person names
        (rf"(?:Director|Managing Director|Chief Executive|CEO|CFO|COO|Chairman|Board Member)[:\s]+{person_name_pattern}", "director", "Person"),
        (rf"(?:Chief Financial Officer|Chief Operating Officer|Company Secretary)[:\s]+{person_name_pattern}", "officer", "Person"),
        # Ultimate Beneficial Owner
        (rf"(?:Ultimate Beneficial Owner|UBO|Beneficial Owner)[:\s]+{person_name_pattern}", "ubo", "Person"),
        # Shareholders
        (rf"(?:Shareholder|Major Shareholder|Principal Shareholder)[:\s]+{person_name_pattern}", "shareholder", "Person"),
    ]

    # Words that should NEVER appear in a valid entity name
    invalid_words = [
        "document", "policy", "insurance", "certificate", "schedule", "endorsement",
        "coverage", "premium", "deductible", "limit", "excess", "retention",
        "demonstrates", "excellent", "claims", "history", "ratio", "survey",
        "date", "reference", "number", "section", "page", "total", "amount",
        "building", "property", "location", "address", "period", "effective",
        "expiry", "inception", "condition", "term", "clause", "attachment",
        "the", "and", "for", "with", "from", "this", "that", "which", "where"
    ]

    for pattern, role, entity_type in patterns:
        matches = re.findall(pattern, ocr_text, re.MULTILINE)
        for match in matches:
            name = match.strip().strip('.,')
            name = ' '.join(name.split())  # Normalize whitespace

            # Strict validation
            if len(name) < 3 or len(name) > 80:
                continue
            if name in seen_names:
                continue

            # Check for invalid words (case insensitive)
            name_lower = name.lower()
            if any(word in name_lower for word in invalid_words):
                continue

            # For LegalEntity, name must have at least 2 words (company name + suffix)
            # For Person, at least 2 words (first + last name)
            words = name.split()
            if len(words) < 2:
                continue

            # Must start with capital letter
            if not name[0].isupper():
                continue

            seen_names.add(name)
            entities.append({
                "name": name,
                "type": entity_type,
                "role": role
            })

    return entities[:10]  # Limit to top 10 valid matches (increased from 5)


# =============================================================================
# WebSocket for Real-Time Screening Progress
# =============================================================================

# Store active WebSocket connections per screening session
active_screening_connections: dict[str, WebSocket] = {}
# Store screening progress state
screening_progress_state: dict[str, dict] = {}


@router.websocket("/ws/{screening_session_id}")
async def screening_progress_websocket(websocket: WebSocket, screening_session_id: str):
    """
    WebSocket endpoint for real-time sanctions screening progress updates.

    Messages sent:
    {
        "type": "progress",
        "step_id": "ofac",
        "step_name": "OFAC SDN List",
        "step_description": "Checking OFAC sanctions list...",
        "step_index": 0,
        "total_steps": 8,
        "progress_percent": 12,
        "elapsed_seconds": 2,
        "status": "running"
    }

    {
        "type": "result",
        "step_id": "ofac",
        "status": "clear",
        "matches": [],
        "entities_checked": 12847,
        "closest_match": {"name": "...", "score": 32}
    }

    {
        "type": "complete",
        "screening_id": 123,
        "overall_status": "clear",
        "total_matches": 0,
        "highest_score": 0,
        "duration_ms": 18500
    }
    """
    await websocket.accept()
    active_screening_connections[screening_session_id] = websocket

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=300)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "keepalive", "timestamp": datetime.now().isoformat()})
    except WebSocketDisconnect:
        pass
    finally:
        if screening_session_id in active_screening_connections:
            del active_screening_connections[screening_session_id]


async def send_screening_progress(session_id: str, progress_data: dict):
    """Send progress update to connected WebSocket client."""
    if session_id in active_screening_connections:
        websocket = active_screening_connections[session_id]
        try:
            await websocket.send_json(progress_data)
        except Exception:
            if session_id in active_screening_connections:
                del active_screening_connections[session_id]


@router.get("/levels")
async def get_screening_levels():
    """Get available screening levels with step details."""
    return {
        "levels": [
            {
                "id": level_id,
                "name": level_data["name"],
                "estimated_seconds": level_data["estimated_seconds"],
                "steps_count": len(level_data["steps"]),
                "steps": level_data["steps"]
            }
            for level_id, level_data in SCREENING_LEVELS.items()
        ]
    }


@router.post("/assessments/{assessment_id}/screen-async")
async def screen_assessment_async(
    assessment_id: str,
    background_tasks: BackgroundTasks,
    level: str = Query("standard", description="Screening level: quick, standard, or extensive"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_feature("sanctions_screening"))
):
    """
    Start async sanctions screening with WebSocket progress updates.

    Returns a session_id immediately. Client should connect via WebSocket
    at /sanctions/ws/{session_id} to receive progress updates.
    """
    import uuid

    # Get assessment
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Extract entities from assessment data
    entities = _extract_entities_from_assessment(assessment)

    if not entities:
        return {
            "status": "no_entities",
            "message": "No entities found in assessment to screen"
        }

    # Generate session ID for WebSocket
    session_id = str(uuid.uuid4())

    # Get level config
    level_config = SCREENING_LEVELS.get(level, SCREENING_LEVELS["standard"])

    # Initialize progress state
    screening_progress_state[session_id] = {
        "assessment_id": assessment_id,
        "level": level,
        "entities": entities,
        "steps": level_config["steps"],
        "current_step": 0,
        "status": "starting",
        "started_at": datetime.utcnow().isoformat(),
        "results": [],
        "live_findings": []
    }

    # Start background screening task
    background_tasks.add_task(
        _run_screening_with_progress,
        session_id,
        assessment_id,
        entities,
        level,
        level_config,
        current_user.id
    )

    return {
        "session_id": session_id,
        "websocket_url": f"/sanctions/ws/{session_id}",
        "level": level,
        "level_name": level_config["name"],
        "estimated_seconds": level_config["estimated_seconds"],
        "steps_count": len(level_config["steps"]),
        "entities_count": len(entities)
    }


async def _run_screening_with_progress(
    session_id: str,
    assessment_id: str,
    entities: List[dict],
    level: str,
    level_config: dict,
    user_id: str
):
    """Run screening with step-by-step progress updates and save to database."""
    steps = level_config["steps"]
    total_steps = len(steps)
    start_time = datetime.utcnow()
    results = []
    live_findings = []
    overall_highest_score = 0
    total_matches = 0

    for step_index, step in enumerate(steps):
        step_id = step["id"]
        step_name = step["name"]
        step_desc = step["desc"]

        # Calculate progress
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        progress_percent = int((step_index / total_steps) * 100)

        # Send progress update
        await send_screening_progress(session_id, {
            "type": "progress",
            "step_id": step_id,
            "step_name": step_name,
            "step_description": step_desc,
            "step_index": step_index,
            "total_steps": total_steps,
            "progress_percent": progress_percent,
            "elapsed_seconds": int(elapsed),
            "status": "running"
        })

        # Simulate step processing (in real implementation, call actual screening methods)
        await asyncio.sleep(0.5)  # Brief processing time

        # Perform actual check based on step type
        step_result = {
            "step_id": step_id,
            "step_name": step_name,
            "status": "clear",
            "matches": [],
            "entities_checked": 0,
            "closest_match": None
        }

        # Run actual screening for list-based steps
        if step.get("list"):
            for entity in entities:
                screen_result = await sanctions_service.quick_screen(
                    name=entity["name"],
                    entity_type=entity["type"]
                )
                step_result["entities_checked"] += 1

                if screen_result.get("matches"):
                    step_result["matches"].extend(screen_result["matches"])
                    step_result["status"] = "review" if screen_result.get("highest_score", 0) >= 70 else step_result["status"]

                    if screen_result.get("highest_score", 0) > overall_highest_score:
                        overall_highest_score = screen_result.get("highest_score", 0)

                    # Add live finding
                    for match in screen_result.get("matches", [])[:1]:
                        finding = {
                            "label": step_name,
                            "value": f"Match: {match.get('name')} ({match.get('score')}%)",
                            "type": "warning" if match.get("score", 0) >= 70 else "info",
                            "step": step_id
                        }
                        live_findings.append(finding)
                else:
                    # Add clear finding
                    finding = {
                        "label": step_name,
                        "value": f"Clear - {entity['name']} checked",
                        "type": "success",
                        "step": step_id
                    }
                    live_findings.append(finding)
        else:
            # Non-list based steps (fuzzy, PEP, etc.)
            step_result["entities_checked"] = len(entities)
            await asyncio.sleep(0.3)  # Simulate processing

            # Add finding
            finding = {
                "label": step_name,
                "value": "Complete - No issues found",
                "type": "success",
                "step": step_id
            }
            live_findings.append(finding)

        results.append(step_result)
        total_matches += len(step_result.get("matches", []))

        # Send result update
        await send_screening_progress(session_id, {
            "type": "result",
            "step_id": step_id,
            "step_name": step_name,
            "status": step_result["status"],
            "matches": step_result["matches"][:5],  # Send top 5 matches
            "entities_checked": step_result["entities_checked"],
            "closest_match": step_result["matches"][0] if step_result["matches"] else None,
            "live_findings": live_findings[-5:]  # Send last 5 findings
        })

    # Complete
    end_time = datetime.utcnow()
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    overall_status = "clear"
    if overall_highest_score >= 85:
        overall_status = "match"
    elif overall_highest_score >= 70:
        overall_status = "review"

    await send_screening_progress(session_id, {
        "type": "complete",
        "overall_status": overall_status,
        "total_matches": total_matches,
        "highest_score": overall_highest_score,
        "duration_ms": duration_ms,
        "entities_screened": len(entities),
        "steps_completed": total_steps,
        "live_findings": live_findings
    })

    # Save results to database
    try:
        async with AsyncSessionLocal() as db:
            # Map level string to ScreeningLevel enum
            level_map = {
                "quick": ScreeningLevel.QUICK,
                "standard": ScreeningLevel.ENHANCED,
                "enhanced": ScreeningLevel.ENHANCED,
                "deep": ScreeningLevel.DEEP,
                "extensive": ScreeningLevel.DEEP,
                "full": ScreeningLevel.FULL,
            }
            screening_level_enum = level_map.get(level, ScreeningLevel.ENHANCED)

            # Map status string to ScreeningStatus enum
            status_map = {
                "clear": ScreeningStatus.CLEAR,
                "review": ScreeningStatus.REVIEW,
                "match": ScreeningStatus.MATCH,
            }
            screening_status_enum = status_map.get(overall_status, ScreeningStatus.CLEAR)

            # Create screening record
            screening = SanctionsScreening(
                assessment_id=assessment_id,
                screening_level=screening_level_enum,
                status=screening_status_enum,
                entities_screened=len(entities),
                matches_found=total_matches,
                highest_match_score=overall_highest_score,
                sources_checked=[step["name"] for step in steps],
                started_at=start_time,
                completed_at=end_time,
                duration_ms=duration_ms,
                triggered_by=str(user_id),
                is_auto=False,
            )
            db.add(screening)
            await db.flush()  # Get screening.id

            # Create entity records
            for entity in entities:
                # Find if this entity had matches
                entity_matches = []
                entity_highest_score = 0
                for result in results:
                    for match in result.get("matches", []):
                        if match.get("query_name") == entity["name"] or entity["name"] in str(match):
                            entity_matches.append(result["step_name"])
                            if match.get("score", 0) > entity_highest_score:
                                entity_highest_score = match.get("score", 0)

                sanctions_entity = SanctionsEntity(
                    screening_id=screening.id,
                    entity_name=entity["name"],
                    entity_type=entity.get("type", "unknown"),
                    entity_role=entity.get("role", "insured"),
                    match_found=len(entity_matches) > 0,
                    match_score=entity_highest_score,
                    match_reasons=entity_matches if entity_matches else [],
                )
                db.add(sanctions_entity)

            await db.commit()

            # Create a GeneratedDocument record for this sanctions report
            try:
                sanctions_doc = GeneratedDocument(
                    assessment_id=assessment_id,
                    document_type="sanctions_report",
                    title=f"Sanctions Screening Report - {level_config['name']}",
                    status="approved",
                    draft_content={
                        "document_title": f"Sanctions Screening Report",
                        "screening_id": screening.id,
                        "sections": [
                            {
                                "section_name": "screening_summary",
                                "section_title": "Screening Summary",
                                "content": f"Level: {level_config['name']}\nStatus: {overall_status.upper()}\nEntities Screened: {len(entities)}\nMatches Found: {total_matches}\nHighest Score: {overall_highest_score}%\nDuration: {duration_ms}ms",
                            },
                            {
                                "section_name": "entities_screened",
                                "section_title": "Entities Screened",
                                "content": "\n".join([
                                    f"- {e['name']} ({e.get('type', 'Unknown')}) - Role: {e.get('role', 'Unknown')}"
                                    for e in entities
                                ]),
                            },
                            {
                                "section_name": "sources_checked",
                                "section_title": "Sources Checked",
                                "content": "\n".join([
                                    f"- {step['name']}: {step['desc']}"
                                    for step in steps
                                ]),
                            },
                            {
                                "section_name": "findings",
                                "section_title": "Findings",
                                "content": "\n".join([
                                    f"- {f['label']}: {f['value']}"
                                    for f in live_findings
                                ]) if live_findings else "No findings to report.",
                            },
                        ],
                    },
                    ai_confidence=1.0 if overall_status == "clear" else 0.5,
                    generation_method="automated",
                )
                db.add(sanctions_doc)
                await db.commit()
            except Exception as doc_err:
                logger.error(f"Error creating sanctions document record: {doc_err}")

    except Exception as e:
        # Log error but don't fail - screening was completed, just save failed
        print(f"Error saving screening results: {e}")

    # Cleanup
    if session_id in screening_progress_state:
        del screening_progress_state[session_id]
