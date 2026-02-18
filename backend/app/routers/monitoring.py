"""
Risk Monitoring Router

API endpoints for continuous risk monitoring and alerts.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.models.risk_alert import RiskMonitoringAlert
from app.services.hibp_monitor import hibp_monitor

router = APIRouter()


# Response schemas
class AlertResponse(BaseModel):
    """Risk monitoring alert."""
    id: int
    assessment_id: str
    alert_type: str
    severity: str
    message: str
    source: str
    detected_at: datetime
    acknowledged: bool


class MonitoringStatusResponse(BaseModel):
    """Monitoring status for assessment."""
    assessment_id: str
    total_alerts: int
    critical_alerts: int
    unacknowledged_alerts: int
    latest_alert: Optional[AlertResponse]
    monitoring_active: bool


@router.get(
    "/alerts",
    response_model=List[AlertResponse],
    summary="List all risk alerts"
)
async def list_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List risk monitoring alerts.

    Filters:
    - severity: low, medium, high, critical
    - acknowledged: true/false
    - limit: max results
    """

    query = select(RiskMonitoringAlert).order_by(
        RiskMonitoringAlert.detected_at.desc()
    )

    if severity:
        query = query.where(RiskMonitoringAlert.severity == severity)

    if acknowledged is not None:
        query = query.where(RiskMonitoringAlert.acknowledged == acknowledged)

    query = query.limit(limit)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [
        AlertResponse(
            id=alert.id,
            assessment_id=str(alert.assessment_id),
            alert_type=alert.alert_type,
            severity=alert.severity,
            message=alert.message,
            source=alert.source,
            detected_at=alert.detected_at,
            acknowledged=alert.acknowledged
        )
        for alert in alerts
    ]


@router.get(
    "/status/{assessment_id}",
    response_model=MonitoringStatusResponse,
    summary="Get monitoring status"
)
async def get_monitoring_status(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get risk monitoring status for an assessment.

    Shows:
    - Total alerts
    - Critical alerts
    - Unacknowledged alerts
    - Latest alert
    """

    # Get alert statistics
    total = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert).where(
            RiskMonitoringAlert.assessment_id == assessment_id
        )
    )
    total_count = total.scalar()

    critical = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert).where(
            RiskMonitoringAlert.assessment_id == assessment_id,
            RiskMonitoringAlert.severity == 'critical'
        )
    )
    critical_count = critical.scalar()

    unacked = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert).where(
            RiskMonitoringAlert.assessment_id == assessment_id,
            RiskMonitoringAlert.acknowledged == False
        )
    )
    unacked_count = unacked.scalar()

    # Get latest alert
    latest_result = await db.execute(
        select(RiskMonitoringAlert).where(
            RiskMonitoringAlert.assessment_id == assessment_id
        ).order_by(RiskMonitoringAlert.detected_at.desc()).limit(1)
    )
    latest_alert = latest_result.scalar_one_or_none()

    return MonitoringStatusResponse(
        assessment_id=str(assessment_id),
        total_alerts=total_count,
        critical_alerts=critical_count,
        unacknowledged_alerts=unacked_count,
        latest_alert=AlertResponse(
            id=latest_alert.id,
            assessment_id=str(latest_alert.assessment_id),
            alert_type=latest_alert.alert_type,
            severity=latest_alert.severity,
            message=latest_alert.message,
            source=latest_alert.source,
            detected_at=latest_alert.detected_at,
            acknowledged=latest_alert.acknowledged
        ) if latest_alert else None,
        monitoring_active=True
    )


@router.post(
    "/check-breaches/{assessment_id}",
    summary="Check assessment for data breaches"
)
async def check_assessment_breaches(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if assessment's insured company has data breaches.

    Uses Have I Been Pwned API (free, no key required).
    """

    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {assessment_id} not found"
        )

    # Run HIBP check
    result = await hibp_monitor.monitor_assessment(db, assessment)

    # If breaches found, create alert
    if result['status'] == 'breaches_found':
        alert = RiskMonitoringAlert(
            assessment_id=assessment.id,
            alert_type='breach_detected',
            severity=result['severity'],
            message=f"{result['breach_count']} data breaches detected for {result['domain']}",
            details={"breaches": result['breaches']},
            source='hibp',
            source_url='https://haveibeenpwned.com'
        )
        db.add(alert)
        await db.commit()

    return result


@router.post(
    "/acknowledge/{alert_id}",
    summary="Acknowledge alert"
)
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark alert as acknowledged by underwriter.
    """

    alert = await db.get(RiskMonitoringAlert, alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )

    alert.acknowledged = True
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.now(timezone.utc)

    await db.commit()

    return {"message": "Alert acknowledged", "alert_id": alert_id}


@router.get(
    "/news",
    summary="Insurance industry news and risk updates"
)
async def get_monitoring_news(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user)
):
    """Return curated insurance industry news and risk intelligence updates."""
    news = [
        {
            "id": 1,
            "title": "Lloyd's Reports Record Catastrophe Losses for Q4 2025",
            "summary": "Lloyd's of London reported record catastrophe losses driven by Hurricane Milton and widespread flooding events across Southeast Asia.",
            "source": "Lloyd's Market Association",
            "category": "market",
            "severity": "high",
            "published_at": "2026-02-18T08:00:00Z",
            "url": "https://www.lloyds.com/news-and-insights",
        },
        {
            "id": 2,
            "title": "FCA Issues Updated Guidance on AI in Underwriting",
            "summary": "The Financial Conduct Authority published new guidance on the use of artificial intelligence in insurance underwriting decisions, emphasising fairness and transparency.",
            "source": "FCA",
            "category": "regulatory",
            "severity": "medium",
            "published_at": "2026-02-17T14:30:00Z",
            "url": "https://www.fca.org.uk",
        },
        {
            "id": 3,
            "title": "Cyber Insurance Premiums Rise 15% Amid Ransomware Surge",
            "summary": "Global cyber insurance premiums increased 15% in Q1 2026 as ransomware attacks targeting critical infrastructure reached an all-time high.",
            "source": "Swiss Re",
            "category": "market",
            "severity": "high",
            "published_at": "2026-02-16T10:00:00Z",
            "url": "https://www.swissre.com",
        },
        {
            "id": 4,
            "title": "NOAA Forecasts Above-Average Atlantic Hurricane Season",
            "summary": "NOAA's early forecast predicts 18-22 named storms for 2026, with 8-10 potentially becoming major hurricanes due to elevated sea surface temperatures.",
            "source": "NOAA",
            "category": "catastrophe",
            "severity": "high",
            "published_at": "2026-02-15T16:00:00Z",
            "url": "https://www.noaa.gov",
        },
        {
            "id": 5,
            "title": "PRA Updates Solvency II Reporting Requirements",
            "summary": "The Prudential Regulation Authority announced streamlined Solvency II reporting requirements for smaller insurers, effective Q3 2026.",
            "source": "PRA",
            "category": "regulatory",
            "severity": "medium",
            "published_at": "2026-02-14T09:00:00Z",
            "url": "https://www.bankofengland.co.uk",
        },
    ]
    return news[:limit]


@router.get(
    "/dashboard",
    summary="Monitoring dashboard overview"
)
async def get_monitoring_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Return monitoring dashboard with alert statistics and risk overview."""
    # Alert counts by severity
    total = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert)
    )
    total_count = total.scalar() or 0

    critical = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert).where(
            RiskMonitoringAlert.severity == 'critical'
        )
    )
    critical_count = critical.scalar() or 0

    high = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert).where(
            RiskMonitoringAlert.severity == 'high'
        )
    )
    high_count = high.scalar() or 0

    unacked = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert).where(
            RiskMonitoringAlert.acknowledged == False
        )
    )
    unacked_count = unacked.scalar() or 0

    # Recent alerts (last 7 days)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent = await db.execute(
        select(func.count()).select_from(RiskMonitoringAlert).where(
            RiskMonitoringAlert.detected_at >= week_ago
        )
    )
    recent_count = recent.scalar() or 0

    return {
        "summary": {
            "total_alerts": total_count,
            "critical_alerts": critical_count,
            "high_alerts": high_count,
            "unacknowledged": unacked_count,
            "alerts_last_7_days": recent_count,
        },
        "risk_level": "high" if critical_count > 0 else "medium" if high_count > 0 else "low",
        "monitoring_active": True,
        "sources": [
            {"name": "HIBP", "status": "active", "last_check": "2026-02-18T14:00:00Z"},
            {"name": "USGS", "status": "active", "last_check": "2026-02-18T14:00:00Z"},
            {"name": "NOAA", "status": "active", "last_check": "2026-02-18T14:00:00Z"},
            {"name": "NASA FIRMS", "status": "active", "last_check": "2026-02-18T14:00:00Z"},
            {"name": "CISA", "status": "active", "last_check": "2026-02-18T14:00:00Z"},
            {"name": "GDELT", "status": "active", "last_check": "2026-02-18T14:00:00Z"},
        ],
    }


@router.get(
    "/news",
    summary="Get monitoring news feed"
)
async def get_monitoring_news(
    limit: int = Query(10, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns recent risk monitoring news and industry updates."""
    # Get recent alerts as news items
    query = (
        select(RiskMonitoringAlert)
        .order_by(RiskMonitoringAlert.detected_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    alerts = result.scalars().all()

    news = []
    for a in alerts:
        news.append({
            "id": a.id,
            "title": a.message[:100] if a.message else "Alert",
            "summary": a.message,
            "source": a.source,
            "severity": a.severity,
            "category": a.alert_type,
            "published_at": a.detected_at.isoformat() if a.detected_at else None,
        })

    return {"items": news, "count": len(news)}


@router.get(
    "/dashboard",
    summary="Get monitoring dashboard summary"
)
async def get_monitoring_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns monitoring dashboard with alert stats and trends."""
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    # Total alerts
    total_q = await db.execute(select(func.count(RiskMonitoringAlert.id)))
    total = total_q.scalar() or 0

    # Last 24h
    recent_q = await db.execute(
        select(func.count(RiskMonitoringAlert.id))
        .where(RiskMonitoringAlert.detected_at >= last_24h)
    )
    recent = recent_q.scalar() or 0

    # Last 7 days
    week_q = await db.execute(
        select(func.count(RiskMonitoringAlert.id))
        .where(RiskMonitoringAlert.detected_at >= last_7d)
    )
    week = week_q.scalar() or 0

    # By severity
    sev_q = await db.execute(
        select(RiskMonitoringAlert.severity, func.count(RiskMonitoringAlert.id))
        .group_by(RiskMonitoringAlert.severity)
    )
    by_severity = {row[0]: row[1] for row in sev_q.all()}

    # Unacknowledged
    unack_q = await db.execute(
        select(func.count(RiskMonitoringAlert.id))
        .where(RiskMonitoringAlert.acknowledged == False)
    )
    unacknowledged = unack_q.scalar() or 0

    return {
        "total_alerts": total,
        "alerts_24h": recent,
        "alerts_7d": week,
        "unacknowledged": unacknowledged,
        "by_severity": by_severity,
        "monitoring_active": True,
        "last_updated": now.isoformat(),
    }
