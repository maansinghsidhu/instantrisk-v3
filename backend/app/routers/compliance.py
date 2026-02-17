"""
InstantRisk V2 - Regulatory Compliance Scanner Router

Endpoints for regulatory compliance checking and regulatory database management.
Scrapes FCA, PRA, EIOPA, and Lloyd's Market Bulletins for up-to-date requirements.

Routes:
    GET  /api/v1/compliance/regulations              - List all regulations
    GET  /api/v1/compliance/regulations/{id}         - Get specific regulation
    GET  /api/v1/compliance/summary                  - Regulatory summary for risk type
    POST /api/v1/compliance/check/{assessment_id}    - Run compliance check on assessment
    GET  /api/v1/compliance/assessments/{id}/report  - Get compliance report for assessment
    POST /api/v1/compliance/scrape                   - Trigger regulatory site scraping
    GET  /api/v1/compliance/updates                  - Get latest scraped regulatory updates
    GET  /api/v1/compliance/scrape/status            - Scraping status
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.services.regulatory_scanner import get_regulatory_scanner

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Schemas
# ============================================================

class ComplianceCheckResponse(BaseModel):
    """Result of a compliance check."""
    assessment_id: str
    checked_at: str
    overall_status: str
    score: int
    passed: int
    failed: int
    warnings: int
    checks: list
    required_actions: List[str]
    regulatory_summary: str


# ============================================================
# Helpers
# ============================================================

async def _load_assessment(assessment_id: str, db: AsyncSession) -> dict:
    """Load assessment data as dict."""
    result = await db.execute(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found",
        )
    return {
        "id": str(assessment.id),
        "title": assessment.title,
        "risk_category": assessment.risk_category,
        "status": assessment.status,
        "decision": assessment.decision,
        "risk_score": assessment.risk_score,
        "sum_insured": assessment.sum_insured,
        "premium": assessment.premium,
        "territory": assessment.territory,
        "inception_date": str(assessment.inception_date) if assessment.inception_date else None,
        "expiry_date": str(assessment.expiry_date) if assessment.expiry_date else None,
        "insured_name": assessment.insured_name,
        "underwriter_notes": assessment.underwriter_notes,
        "broker_name": getattr(assessment, "broker_name", None),
        "regulatory_framework": getattr(assessment, "regulatory_framework", None),
    }


# ============================================================
# Endpoints
# ============================================================

@router.get(
    "/regulations",
    summary="List regulatory requirements",
)
async def list_regulations(
    regulator: Optional[str] = Query(None, description="Filter by: FCA | PRA | EIOPA | LLOYD'S | ICO"),
    category: Optional[str] = Query(None, description="Filter by: conduct | prudential | reporting | consumer | data | solvency"),
    risk_category: Optional[str] = Query(None, description="Filter by risk type: property | cyber | marine | liability | financial_lines"),
    severity: Optional[str] = Query(None, description="Filter by: critical | high | medium | low"),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the full regulatory database, with optional filtering.

    The database includes requirements from:
    - FCA (Financial Conduct Authority)
    - PRA (Prudential Regulation Authority)
    - EIOPA (European Insurance & Occupational Pensions Authority)
    - Lloyd's of London Market Bulletins
    - ICO (GDPR data protection)

    All regulations are categorised by risk type, severity, and regulatory body.
    """
    scanner = get_regulatory_scanner()
    regs = scanner.get_regulations(
        regulator=regulator,
        category=category,
        risk_category=risk_category,
        severity=severity,
    )
    return {
        "regulations": regs,
        "count": len(regs),
        "filters_applied": {
            "regulator": regulator,
            "category": category,
            "risk_category": risk_category,
            "severity": severity,
        },
    }


@router.get(
    "/regulations/{reg_id}",
    summary="Get a specific regulation",
)
async def get_regulation(
    reg_id: str,
    current_user: User = Depends(get_current_user),
):
    """Returns details of a specific regulation by ID (e.g. FCA-ICOBS-6, LLO-MB-Y5387)."""
    scanner = get_regulatory_scanner()
    all_regs = scanner.get_regulations()
    reg = next((r for r in all_regs if r["reg_id"] == reg_id), None)
    if not reg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regulation {reg_id} not found",
        )
    return reg


@router.get(
    "/summary",
    summary="Get regulatory summary for a risk type",
)
async def get_regulatory_summary(
    risk_category: str = Query(
        "property",
        description="Risk type: property | cyber | marine | liability | financial_lines",
    ),
    territory: str = Query("UK", description="Territory: UK | EU | USA | Global"),
    current_user: User = Depends(get_current_user),
):
    """
    Returns a curated regulatory summary for a specific risk type and territory.

    Useful for underwriters to quickly understand which regulators and key
    requirements apply before starting a new assessment.
    """
    scanner = get_regulatory_scanner()
    return scanner.get_regulatory_summary(risk_category=risk_category, territory=territory)


@router.post(
    "/check/{assessment_id}",
    response_model=ComplianceCheckResponse,
    summary="Run regulatory compliance check on an assessment",
)
async def check_assessment_compliance(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Runs a full regulatory compliance check on an assessment.

    Checks the assessment against all applicable regulations based on:
    - Risk category (property/cyber/marine/liability/financial lines)
    - Territory (UK/EU/Global)
    - Sum insured and risk score

    Returns pass/fail for each regulation, required actions, and overall compliance score.

    Compliance score:
    - 90-100: Compliant (minor warnings only)
    - 70-89: Requires action (significant warnings)
    - 50-69: Requires action (multiple issues)
    - Below 50: Critical issues (block binding)
    """
    assessment_data = await _load_assessment(assessment_id, db)
    scanner = get_regulatory_scanner()
    result = await scanner.check_assessment_compliance(assessment_data)

    return ComplianceCheckResponse(
        assessment_id=result.assessment_id,
        checked_at=result.checked_at,
        overall_status=result.overall_status,
        score=result.score,
        passed=result.passed,
        failed=result.failed,
        warnings=result.warnings,
        checks=result.checks,
        required_actions=result.required_actions,
        regulatory_summary=result.regulatory_summary,
    )


@router.get(
    "/assessments/{assessment_id}/report",
    summary="Get full compliance report for an assessment",
)
async def get_compliance_report(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates and returns a comprehensive compliance report for an assessment.

    Includes:
    - Full compliance check results with pass/fail per regulation
    - Risk-category specific regulatory summary
    - Required actions prioritised by severity
    - Recommended next steps
    """
    assessment_data = await _load_assessment(assessment_id, db)
    scanner = get_regulatory_scanner()

    check = await scanner.check_assessment_compliance(assessment_data)
    regulatory_summary = scanner.get_regulatory_summary(
        risk_category=assessment_data.get("risk_category", "property"),
        territory=assessment_data.get("territory", "UK"),
    )

    # Group checks by regulator
    by_regulator: dict = {}
    for c in check.checks:
        reg = c.get("regulator", "Other")
        if reg not in by_regulator:
            by_regulator[reg] = {"passed": 0, "warnings": 0, "failed": 0, "checks": []}
        by_regulator[reg]["checks"].append(c)
        by_regulator[reg][c["status"]] = by_regulator[reg].get(c["status"], 0) + 1

    # Recommended next steps
    next_steps = []
    if check.overall_status == "critical_issues":
        next_steps.append("STOP: Do not bind until all critical compliance issues are resolved")
    if check.failed > 0:
        next_steps.append("Resolve all FAILED compliance checks before proceeding")
    if check.warnings > 0:
        next_steps.append("Address all WARNING items and document compliance steps taken")
    next_steps.extend(check.required_actions[:5])
    if not next_steps:
        next_steps.append("Compliance requirements met. Document evidence of checks completed.")

    return {
        "assessment_id": assessment_id,
        "assessment_title": assessment_data.get("title", ""),
        "risk_category": assessment_data.get("risk_category", ""),
        "territory": assessment_data.get("territory", "UK"),
        "compliance_check": {
            "checked_at": check.checked_at,
            "overall_status": check.overall_status,
            "compliance_score": check.score,
            "summary": check.regulatory_summary,
            "by_regulator": by_regulator,
            "all_checks": check.checks,
        },
        "regulatory_context": regulatory_summary,
        "required_actions": check.required_actions,
        "next_steps": next_steps,
        "generated_at": check.checked_at,
    }


@router.post(
    "/scrape",
    summary="Trigger live regulatory website scraping",
)
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Triggers a live scrape of FCA, PRA, EIOPA, and Lloyd's websites
    to fetch the latest regulatory publications and market bulletins.

    Scraping runs as a background task. Check GET /scrape/status for progress.
    Results are cached and used to supplement the embedded regulatory database.

    Rate limited: scrapes are only refreshed after the configured interval (24h by default).
    """
    scanner = get_regulatory_scanner()

    if scanner._scrape_in_progress:
        return {
            "status": "already_running",
            "message": "Scrape already in progress. Check GET /compliance/scrape/status",
        }

    background_tasks.add_task(scanner.scrape_all_regulators)

    return {
        "status": "started",
        "message": "Regulatory scraping started in background",
        "sources": ["FCA", "PRA", "EIOPA", "Lloyd's Market Bulletins"],
        "check_status": "GET /api/v1/compliance/scrape/status",
    }


@router.get(
    "/scrape/status",
    summary="Regulatory scraping status",
)
async def get_scrape_status(
    current_user: User = Depends(get_current_user),
):
    """Returns current status of the regulatory scraping system."""
    scanner = get_regulatory_scanner()
    return scanner.get_scrape_status()


@router.get(
    "/updates",
    summary="Latest scraped regulatory updates",
)
async def get_regulatory_updates(
    limit: int = Query(20, le=100, description="Number of updates to return"),
    regulator: Optional[str] = Query(None, description="Filter by regulator"),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the most recently scraped regulatory updates and publications.

    Data comes from live scraping of:
    - FCA news and publications
    - PRA/Bank of England publications
    - EIOPA publications
    - Lloyd's market bulletins

    Trigger a fresh scrape with POST /compliance/scrape.
    """
    scanner = get_regulatory_scanner()
    updates = scanner.get_regulatory_updates(limit=limit * 2)

    if regulator:
        updates = [u for u in updates if u.get("regulator", "").upper() == regulator.upper()]

    return {
        "updates": updates[:limit],
        "count": len(updates[:limit]),
        "last_scraped": scanner._last_scraped,
        "next_scrape_due": (
            "Overdue - trigger with POST /compliance/scrape"
            if scanner.get_scrape_status()["needs_rescrape"]
            else f"Within {scanner.SCRAPE_INTERVAL_HOURS}h of last scrape"
        ),
    }


@router.get(
    "/regulators",
    summary="List configured regulatory sources",
)
async def list_regulators(
    current_user: User = Depends(get_current_user),
):
    """Returns all regulatory sources configured in the compliance scanner."""
    return {
        "regulators": [
            {
                "id": "FCA",
                "name": "Financial Conduct Authority",
                "jurisdiction": "UK",
                "url": "https://www.fca.org.uk",
                "focus": "Conduct of business, consumer protection, market integrity",
                "key_requirements": ["ICOBS", "Consumer Duty", "SYSC", "PROD"],
            },
            {
                "id": "PRA",
                "name": "Prudential Regulation Authority",
                "jurisdiction": "UK",
                "url": "https://www.bankofengland.co.uk/prudential-regulation",
                "focus": "Financial soundness, capital adequacy, systemic risk",
                "key_requirements": ["Solvency II", "Operational Resilience", "Stress Testing"],
            },
            {
                "id": "EIOPA",
                "name": "European Insurance & Occupational Pensions Authority",
                "jurisdiction": "EU",
                "url": "https://www.eiopa.europa.eu",
                "focus": "Pan-European insurance supervision, Solvency II implementation",
                "key_requirements": ["SFCR", "IDD", "ORSA", "ESG Integration"],
            },
            {
                "id": "LLOYD'S",
                "name": "Lloyd's of London",
                "jurisdiction": "UK/Global",
                "url": "https://www.lloyds.com",
                "focus": "Market standards, aggregate management, syndicate oversight",
                "key_requirements": ["Market Bulletins", "Minimum Standards", "Performance Management"],
            },
            {
                "id": "ICO",
                "name": "Information Commissioner's Office",
                "jurisdiction": "UK",
                "url": "https://ico.org.uk",
                "focus": "UK GDPR, data protection, privacy",
                "key_requirements": ["ROPA", "Breach Notification", "Data Subject Rights", "DPIA"],
            },
        ]
    }
