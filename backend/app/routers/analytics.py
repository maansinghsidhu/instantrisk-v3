"""
InstantRisk V2 - Portfolio Analytics Router

CFO-grade real-time portfolio dashboards powered by DuckDB OLAP.

Endpoints:
  GET /api/v1/analytics/portfolio          - Full dashboard (all metrics combined)
  GET /api/v1/analytics/exposure-by-territory
  GET /api/v1/analytics/concentration-risk
  GET /api/v1/analytics/renewal-pipeline
  GET /api/v1/analytics/forecasts

All responses return JSON dicts ready for Plotly frontend charts.
Authentication: Bearer JWT required for all endpoints.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.portfolio_analytics import portfolio_analytics

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _run_analytics(coro):
    """Run an analytics coroutine and wrap any errors in HTTP 500."""
    try:
        return await coro
    except Exception as exc:
        logger.exception("Portfolio analytics error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analytics computation failed: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/portfolio",
    summary="Full CFO portfolio dashboard",
    description=(
        "Returns all portfolio analytics in a single response: KPIs, exposure by territory, "
        "concentration risk (HHI), renewal pipeline, win rates, loss ratios, and premium forecasts. "
        "Data is computed in-memory via DuckDB OLAP over the PostgreSQL assessments table."
    ),
    tags=["Portfolio Analytics"],
)
async def get_portfolio_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    **CFO Dashboard** - full portfolio analytics in one call.

    Response shape:
    ```json
    {
      "status": "ok",
      "kpis": {
        "total_assessments": 142,
        "bound": 89,
        "total_premium": 4500000.0,
        "total_tsi": 310000000.0,
        "win_rate_pct": 73.5,
        ...
      },
      "exposure_by_territory": [...],
      "concentration_risk": { "territory": {...}, "risk_category": {...} },
      "renewal_pipeline": { "total_renewals": 12, "buckets": {...}, "renewals": [...] },
      "win_rates": { "overall": {...}, "by_territory": [...], "monthly_trend": [...] },
      "loss_ratios": { "overall": {...}, "by_territory": [...] },
      "forecasts": { "method": "prophet", "forecast": [...] },
      "generated_at": "2026-02-18T12:00:00+00:00"
    }
    ```
    """
    return await _run_analytics(
        portfolio_analytics.get_portfolio_dashboard(db)
    )


@router.get(
    "/exposure-by-territory",
    summary="Exposure aggregated by territory",
    description=(
        "Returns total premium, total sum insured, assessment count, and bound/declined counts "
        "for each territory. Includes a premium_share percentage for Plotly pie/bar charts."
    ),
    tags=["Portfolio Analytics"],
)
async def get_exposure_by_territory(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Territory exposure breakdown.

    Response shape:
    ```json
    {
      "territories": [
        {
          "territory": "UK",
          "assessment_count": 45,
          "total_premium": 1800000.0,
          "total_sum_insured": 120000000.0,
          "avg_risk_score": 42.3,
          "premium_share": 40.0,
          "bound_count": 33,
          "declined_count": 12
        },
        ...
      ],
      "total_assessments": 142,
      "total_premium": 4500000.0,
      "total_tsi": 310000000.0,
      "generated_at": "..."
    }
    ```

    Plotly usage:
    ```js
    // Pie chart of premium by territory
    Plotly.newPlot('chart', [{
      values: data.territories.map(t => t.total_premium),
      labels: data.territories.map(t => t.territory),
      type: 'pie'
    }])
    ```
    """
    return await _run_analytics(
        portfolio_analytics.get_exposure_by_territory(db)
    )


@router.get(
    "/concentration-risk",
    summary="Concentration risk via Herfindahl-Hirschman Index",
    description=(
        "Computes HHI scores for portfolio concentration by territory and risk category. "
        "HHI < 0.15 = Diversified, 0.15-0.25 = Moderate, > 0.25 = Concentrated."
    ),
    tags=["Portfolio Analytics"],
)
async def get_concentration_risk(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Herfindahl-Hirschman Index concentration analysis.

    Response shape:
    ```json
    {
      "territory": {
        "hhi": 0.18,
        "rating": "Moderate",
        "top_segments": [
          { "segment": "UK", "premium": 1800000.0, "tsi": 120000000.0, "share_pct": 40.0 },
          ...
        ]
      },
      "risk_category": {
        "hhi": 0.22,
        "rating": "Moderate",
        "top_segments": [...]
      },
      "overall_hhi": 0.20,
      "generated_at": "..."
    }
    ```

    Plotly usage:
    ```js
    // Gauge chart for HHI
    Plotly.newPlot('gauge', [{
      type: 'indicator', mode: 'gauge+number',
      value: data.overall_hhi,
      gauge: { axis: { range: [0, 0.5] } }
    }])
    ```
    """
    return await _run_analytics(
        portfolio_analytics.get_concentration_risk(db)
    )


@router.get(
    "/renewal-pipeline",
    summary="Renewal pipeline for expiring policies",
    description=(
        "Returns policies expiring within the specified horizon (default 90 days), "
        "bucketed into 0-30, 31-60, 61-90 day windows. "
        "Includes total premium at risk and individual policy details."
    ),
    tags=["Portfolio Analytics"],
)
async def get_renewal_pipeline(
    horizon_days: int = Query(
        90,
        ge=1,
        le=365,
        description="Number of days ahead to look for expiring policies (1-365)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Policy renewal pipeline.

    Response shape:
    ```json
    {
      "horizon_days": 90,
      "total_renewals": 12,
      "total_premium_at_risk": 650000.0,
      "buckets": {
        "0_30_days": { "count": 3, "total_premium": 180000.0, "total_tsi": 12000000.0 },
        "31_60_days": { "count": 5, "total_premium": 280000.0, "total_tsi": 18000000.0 },
        "61_90_days": { "count": 4, "total_premium": 190000.0, "total_tsi": 14000000.0 }
      },
      "renewals": [
        {
          "id": "...",
          "insured_name": "Acme Corp",
          "territory": "UK",
          "premium": 60000.0,
          "expiry_date": "2026-02-28",
          "days_to_expiry": 10
        },
        ...
      ],
      "generated_at": "..."
    }
    ```

    Plotly usage:
    ```js
    // Bar chart of renewal buckets
    const buckets = data.buckets;
    Plotly.newPlot('renewals', [{
      x: ['0-30 days', '31-60 days', '61-90 days'],
      y: [buckets['0_30_days'].total_premium, buckets['31_60_days'].total_premium, buckets['61_90_days'].total_premium],
      type: 'bar', name: 'Premium at Risk'
    }])
    ```
    """
    return await _run_analytics(
        portfolio_analytics.get_renewal_pipeline(db, horizon_days=horizon_days)
    )


@router.get(
    "/forecasts",
    summary="Prophet-based premium trend forecasting",
    description=(
        "Forecasts monthly bound premium for the next N months using Facebook Prophet. "
        "Falls back to linear extrapolation if Prophet is unavailable or data is insufficient. "
        "Returns historical actuals + future predictions with confidence intervals."
    ),
    tags=["Portfolio Analytics"],
)
async def get_forecasts(
    horizon_months: int = Query(
        12,
        ge=1,
        le=36,
        description="Number of months to forecast ahead (1-36)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Premium trend forecasting.

    Response shape:
    ```json
    {
      "method": "prophet",
      "horizon_months": 12,
      "total_predicted_premium": 6200000.0,
      "avg_monthly_predicted": 516666.67,
      "historical": [
        { "month": "2025-03", "actual_premium": 420000.0 },
        ...
      ],
      "forecast": [
        {
          "month": "2026-03",
          "predicted_premium": 520000.0,
          "lower_bound": 380000.0,
          "upper_bound": 660000.0
        },
        ...
      ],
      "generated_at": "..."
    }
    ```

    Plotly usage:
    ```js
    // Time series with confidence band
    Plotly.newPlot('forecast', [
      { x: data.historical.map(h => h.month), y: data.historical.map(h => h.actual_premium), name: 'Actual', mode: 'lines' },
      { x: data.forecast.map(f => f.month), y: data.forecast.map(f => f.predicted_premium), name: 'Forecast', mode: 'lines', line: { dash: 'dot' } },
      { x: [...data.forecast.map(f => f.month), ...data.forecast.map(f => f.month).reverse()],
        y: [...data.forecast.map(f => f.upper_bound), ...data.forecast.map(f => f.lower_bound).reverse()],
        fill: 'toself', fillcolor: 'rgba(0,100,80,0.2)', name: '80% CI', type: 'scatter' }
    ])
    ```
    """
    return await _run_analytics(
        portfolio_analytics.get_forecasts(db, horizon_months=horizon_months)
    )


@router.get(
    "/win-rates",
    summary="Win rate analysis by territory and category",
    description=(
        "Returns GO/NO-GO decision ratios broken down by overall, territory, risk category, "
        "and monthly trend. Useful for underwriter performance dashboards."
    ),
    tags=["Portfolio Analytics"],
)
async def get_win_rates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Win rate breakdown for underwriter performance tracking.

    Returns the win_rates sub-section from the full dashboard.
    """
    from app.services.portfolio_analytics import PortfolioAnalyticsService
    svc = PortfolioAnalyticsService()
    assessments_df = await svc._fetch_assessments(db)
    losses_df = await svc._fetch_losses(db)

    if assessments_df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No assessment data available for win rate analysis.",
        )

    conn = svc._duck_conn()
    svc._register_frames(conn, assessments_df, losses_df)
    try:
        data = svc._win_rates(conn)
    except Exception as exc:
        logger.exception("Win rate calculation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Win rate calculation failed: {str(exc)}",
        )
    finally:
        conn.close()

    from datetime import datetime, timezone
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    return data


@router.get(
    "/loss-ratios",
    summary="Loss ratio analysis by territory and category",
    description=(
        "Calculates incurred losses / earned premium ratios for bound policies. "
        "Requires exposure_losses data to be present. "
        "Returns overall and segmented loss ratios for actuarial review."
    ),
    tags=["Portfolio Analytics"],
)
async def get_loss_ratios(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Loss ratio analysis.

    Returns the loss_ratios sub-section from the full dashboard.
    """
    from app.services.portfolio_analytics import PortfolioAnalyticsService
    svc = PortfolioAnalyticsService()
    assessments_df = await svc._fetch_assessments(db)
    losses_df = await svc._fetch_losses(db)

    if assessments_df.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No assessment data available for loss ratio analysis.",
        )

    conn = svc._duck_conn()
    svc._register_frames(conn, assessments_df, losses_df)
    try:
        data = svc._loss_ratios(conn, losses_df)
    except Exception as exc:
        logger.exception("Loss ratio calculation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Loss ratio calculation failed: {str(exc)}",
        )
    finally:
        conn.close()

    from datetime import datetime, timezone
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    return data
