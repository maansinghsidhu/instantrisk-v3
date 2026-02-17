"""
InstantRisk V2 - Portfolio Analytics Service

DuckDB-powered in-memory OLAP analytics for CFO-grade portfolio dashboards.
Queries PostgreSQL assessments, aggregates with DuckDB, and optionally
forecasts premium trends with Prophet.

Key metrics:
  - Exposure by territory (sum_insured, premium, count)
  - Concentration risk (Herfindahl-Hirschman Index per territory / category)
  - Renewal pipeline (assessments expiring within N days)
  - Win rates (GO decisions / total completed)
  - Loss ratios (total incurred losses / earned premium)
  - Prophet-based premium trend forecasting (12-month horizon)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import duckdb
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float | None:
    """Convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rows_to_df(rows: list[Any], columns: list[str]) -> pd.DataFrame:
    """Convert SQLAlchemy Row objects to a DataFrame."""
    return pd.DataFrame([dict(zip(columns, r)) for r in rows])


# ---------------------------------------------------------------------------
# Core OLAP class
# ---------------------------------------------------------------------------

class PortfolioAnalyticsService:
    """
    Executes portfolio analytics using DuckDB in-memory OLAP.

    Pattern:
      1. Fetch raw rows from PostgreSQL via SQLAlchemy (async).
      2. Load into a DuckDB in-memory database.
      3. Run analytical SQL against DuckDB (window functions, aggregations).
      4. Return plain dicts/lists ready for JSON serialisation.
    """

    # ------------------------------------------------------------------
    # 1. Raw data fetchers
    # ------------------------------------------------------------------

    async def _fetch_assessments(self, db: AsyncSession) -> pd.DataFrame:
        """
        Pull all non-cancelled assessments from PostgreSQL.
        Returns a DataFrame with columns used across all analytics.
        """
        sql = text("""
            SELECT
                a.id::text                          AS id,
                a.reference_number,
                a.title,
                a.risk_category,
                a.status,
                a.decision,
                a.insured_name,
                a.broker_name,
                COALESCE(a.premium, 0)              AS premium,
                COALESCE(a.sum_insured, 0)          AS sum_insured,
                COALESCE(a.deductible, 0)           AS deductible,
                COALESCE(a.commission_rate, 0)      AS commission_rate,
                a.inception_date,
                a.expiry_date,
                a.renewal_date,
                a.territory,
                a.risk_score,
                a.confidence_score,
                a.created_at,
                a.completed_at,
                u.email                             AS underwriter_email
            FROM assessments a
            LEFT JOIN users u ON u.id = a.created_by
            WHERE a.status NOT IN ('cancelled', 'failed')
              AND a.title IS NOT NULL
            ORDER BY a.created_at DESC
        """)
        result = await db.execute(sql)
        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()

        cols = [
            "id", "reference_number", "title", "risk_category", "status",
            "decision", "insured_name", "broker_name", "premium", "sum_insured",
            "deductible", "commission_rate", "inception_date", "expiry_date",
            "renewal_date", "territory", "risk_score", "confidence_score",
            "created_at", "completed_at", "underwriter_email",
        ]
        df = _rows_to_df(rows, cols)

        # Normalise types
        for col in ("premium", "sum_insured", "deductible", "commission_rate"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        for col in ("inception_date", "expiry_date", "renewal_date", "created_at", "completed_at"):
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

        df["territory"] = df["territory"].fillna("Unknown")
        df["risk_category"] = df["risk_category"].fillna("property")
        df["broker_name"] = df["broker_name"].fillna("Unknown Broker")

        return df

    async def _fetch_losses(self, db: AsyncSession) -> pd.DataFrame:
        """Pull exposure losses for loss-ratio calculations."""
        sql = text("""
            SELECT
                l.assessment_id::text   AS assessment_id,
                CAST(l.loss_amount AS DOUBLE PRECISION) AS loss_amount,
                l.currency,
                l.loss_type,
                l.territory,
                l.class_of_business,
                l.loss_date,
                l.created_at
            FROM exposure_losses l
        """)
        result = await db.execute(sql)
        rows = result.fetchall()
        if not rows:
            return pd.DataFrame(columns=[
                "assessment_id", "loss_amount", "currency", "loss_type",
                "territory", "class_of_business", "loss_date", "created_at",
            ])
        cols = [
            "assessment_id", "loss_amount", "currency", "loss_type",
            "territory", "class_of_business", "loss_date", "created_at",
        ]
        df = _rows_to_df(rows, cols)
        df["loss_amount"] = pd.to_numeric(df["loss_amount"], errors="coerce").fillna(0.0)
        df["loss_date"] = pd.to_datetime(df["loss_date"], utc=True, errors="coerce")
        return df

    # ------------------------------------------------------------------
    # 2. DuckDB helper
    # ------------------------------------------------------------------

    def _duck_conn(self) -> duckdb.DuckDBPyConnection:
        """Return a fresh in-memory DuckDB connection."""
        return duckdb.connect(database=":memory:")

    def _register_frames(
        self,
        conn: duckdb.DuckDBPyConnection,
        assessments: pd.DataFrame,
        losses: pd.DataFrame,
    ) -> None:
        """Register DataFrames as virtual DuckDB tables."""
        conn.register("assessments", assessments)
        conn.register("losses", losses)

    # ------------------------------------------------------------------
    # 3. Individual analytics
    # ------------------------------------------------------------------

    def _exposure_by_territory(
        self, conn: duckdb.DuckDBPyConnection
    ) -> list[dict]:
        """
        Aggregate sum_insured, premium, and count by territory.
        Also computes average risk score per territory.
        """
        sql = """
            SELECT
                territory,
                COUNT(*)                                        AS assessment_count,
                SUM(premium)                                    AS total_premium,
                SUM(sum_insured)                                AS total_sum_insured,
                AVG(risk_score)                                 AS avg_risk_score,
                SUM(premium) / NULLIF(SUM(SUM(premium)) OVER (), 0) AS premium_share,
                COUNT(CASE WHEN decision = 'go' THEN 1 END)    AS bound_count,
                COUNT(CASE WHEN decision = 'no_go' THEN 1 END) AS declined_count
            FROM assessments
            WHERE territory IS NOT NULL
            GROUP BY territory
            ORDER BY total_premium DESC
        """
        rows = conn.execute(sql).fetchall()
        cols = [
            "territory", "assessment_count", "total_premium",
            "total_sum_insured", "avg_risk_score", "premium_share",
            "bound_count", "declined_count",
        ]
        result = []
        for r in rows:
            record = dict(zip(cols, r))
            record["premium_share"] = round((_safe_float(record["premium_share"]) or 0) * 100, 2)
            record["avg_risk_score"] = round(_safe_float(record["avg_risk_score"]) or 0, 1)
            record["total_premium"] = round(_safe_float(record["total_premium"]) or 0, 2)
            record["total_sum_insured"] = round(_safe_float(record["total_sum_insured"]) or 0, 2)
            result.append(record)
        return result

    def _concentration_risk(
        self, conn: duckdb.DuckDBPyConnection
    ) -> dict:
        """
        Herfindahl-Hirschman Index (HHI) for territory and risk_category.

        HHI = sum(s_i^2) where s_i = share of premium from segment i.
        HHI < 0.15  => not concentrated
        HHI 0.15-0.25 => moderately concentrated
        HHI > 0.25  => highly concentrated

        Returns HHI scores + top-5 concentrations for both dimensions.
        """
        def _hhi(dimension: str) -> tuple[float, list[dict]]:
            sql = f"""
                WITH totals AS (
                    SELECT
                        {dimension}                            AS segment,
                        SUM(premium)                           AS seg_premium,
                        SUM(sum_insured)                       AS seg_tsi
                    FROM assessments
                    GROUP BY {dimension}
                ),
                shares AS (
                    SELECT
                        segment,
                        seg_premium,
                        seg_tsi,
                        seg_premium / NULLIF(SUM(seg_premium) OVER (), 0) AS premium_share
                    FROM totals
                )
                SELECT
                    segment,
                    seg_premium,
                    seg_tsi,
                    premium_share,
                    premium_share * premium_share                          AS hhi_component
                FROM shares
                ORDER BY premium_share DESC
            """
            rows = conn.execute(sql).fetchall()
            cols = ["segment", "seg_premium", "seg_tsi", "premium_share", "hhi_component"]
            records = [dict(zip(cols, r)) for r in rows]
            hhi_value = sum(r["hhi_component"] or 0 for r in records)

            top5 = []
            for r in records[:5]:
                top5.append({
                    "segment": r["segment"],
                    "premium": round(_safe_float(r["seg_premium"]) or 0, 2),
                    "tsi": round(_safe_float(r["seg_tsi"]) or 0, 2),
                    "share_pct": round((_safe_float(r["premium_share"]) or 0) * 100, 2),
                })
            return round(hhi_value, 4), top5

        territory_hhi, territory_top5 = _hhi("territory")
        category_hhi, category_top5 = _hhi("risk_category")

        def _rating(hhi: float) -> str:
            if hhi < 0.15:
                return "Diversified"
            if hhi < 0.25:
                return "Moderate"
            return "Concentrated"

        return {
            "territory": {
                "hhi": territory_hhi,
                "rating": _rating(territory_hhi),
                "top_segments": territory_top5,
            },
            "risk_category": {
                "hhi": category_hhi,
                "rating": _rating(category_hhi),
                "top_segments": category_top5,
            },
            "overall_hhi": round((territory_hhi + category_hhi) / 2, 4),
        }

    def _renewal_pipeline(
        self, conn: duckdb.DuckDBPyConnection, horizon_days: int = 90
    ) -> dict:
        """
        Identify policies expiring within `horizon_days`.

        Buckets: 0-30 days, 31-60 days, 61-90 days.
        Also returns per-policy renewal details sorted by premium descending.
        """
        sql = f"""
            SELECT
                id,
                reference_number,
                insured_name,
                broker_name,
                territory,
                risk_category,
                premium,
                sum_insured,
                expiry_date,
                renewal_date,
                decision,
                status,
                DATEDIFF('day', CURRENT_DATE, CAST(expiry_date AS DATE)) AS days_to_expiry
            FROM assessments
            WHERE expiry_date IS NOT NULL
              AND CAST(expiry_date AS DATE) >= CURRENT_DATE
              AND DATEDIFF('day', CURRENT_DATE, CAST(expiry_date AS DATE)) <= {horizon_days}
            ORDER BY days_to_expiry ASC
        """
        rows = conn.execute(sql).fetchall()
        cols = [
            "id", "reference_number", "insured_name", "broker_name",
            "territory", "risk_category", "premium", "sum_insured",
            "expiry_date", "renewal_date", "decision", "status", "days_to_expiry",
        ]
        records = []
        for r in rows:
            rec = dict(zip(cols, r))
            rec["premium"] = round(_safe_float(rec["premium"]) or 0, 2)
            rec["sum_insured"] = round(_safe_float(rec["sum_insured"]) or 0, 2)
            rec["expiry_date"] = str(rec["expiry_date"])[:10] if rec["expiry_date"] else None
            rec["renewal_date"] = str(rec["renewal_date"])[:10] if rec["renewal_date"] else None
            records.append(rec)

        bucket_0_30 = [r for r in records if 0 <= (r["days_to_expiry"] or 999) <= 30]
        bucket_31_60 = [r for r in records if 31 <= (r["days_to_expiry"] or 999) <= 60]
        bucket_61_90 = [r for r in records if 61 <= (r["days_to_expiry"] or 999) <= 90]

        def _bucket_summary(items: list[dict]) -> dict:
            return {
                "count": len(items),
                "total_premium": round(sum(r["premium"] for r in items), 2),
                "total_tsi": round(sum(r["sum_insured"] for r in items), 2),
            }

        return {
            "horizon_days": horizon_days,
            "total_renewals": len(records),
            "total_premium_at_risk": round(sum(r["premium"] for r in records), 2),
            "buckets": {
                "0_30_days": _bucket_summary(bucket_0_30),
                "31_60_days": _bucket_summary(bucket_31_60),
                "61_90_days": _bucket_summary(bucket_61_90),
            },
            "renewals": records[:50],  # cap at 50 for JSON response size
        }

    def _win_rates(self, conn: duckdb.DuckDBPyConnection) -> dict:
        """
        Win rate = GO decisions / (GO + NO_GO) for completed assessments.

        Broken down by: overall, territory, risk_category, broker_name, month.
        """
        # Overall
        overall_sql = """
            SELECT
                COUNT(*)                                                    AS total_completed,
                COUNT(CASE WHEN decision = 'go'    THEN 1 END)             AS bound,
                COUNT(CASE WHEN decision = 'no_go' THEN 1 END)             AS declined,
                COUNT(CASE WHEN decision = 'pending' THEN 1 END)           AS pending,
                ROUND(
                    COUNT(CASE WHEN decision = 'go' THEN 1 END) * 100.0
                    / NULLIF(COUNT(CASE WHEN decision IN ('go','no_go') THEN 1 END), 0),
                    2
                )                                                           AS win_rate_pct,
                SUM(CASE WHEN decision = 'go' THEN premium ELSE 0 END)     AS bound_premium,
                AVG(CASE WHEN decision = 'go' THEN risk_score END)         AS avg_bound_risk_score
            FROM assessments
            WHERE status NOT IN ('draft', 'cancelled', 'failed')
        """
        row = conn.execute(overall_sql).fetchone()
        overall = {
            "total_completed": row[0],
            "bound": row[1],
            "declined": row[2],
            "pending": row[3],
            "win_rate_pct": _safe_float(row[4]) or 0.0,
            "bound_premium": round(_safe_float(row[5]) or 0, 2),
            "avg_bound_risk_score": round(_safe_float(row[6]) or 0, 1),
        }

        # By territory
        territory_sql = """
            SELECT
                territory,
                COUNT(*)                                                        AS total,
                COUNT(CASE WHEN decision = 'go' THEN 1 END)                    AS bound,
                ROUND(
                    COUNT(CASE WHEN decision = 'go' THEN 1 END) * 100.0
                    / NULLIF(COUNT(CASE WHEN decision IN ('go','no_go') THEN 1 END), 0),
                    2
                )                                                               AS win_rate_pct,
                SUM(CASE WHEN decision = 'go' THEN premium ELSE 0 END)         AS bound_premium
            FROM assessments
            WHERE status NOT IN ('draft', 'cancelled', 'failed')
            GROUP BY territory
            ORDER BY bound_premium DESC
        """
        by_territory = []
        for r in conn.execute(territory_sql).fetchall():
            by_territory.append({
                "territory": r[0],
                "total": r[1],
                "bound": r[2],
                "win_rate_pct": _safe_float(r[3]) or 0.0,
                "bound_premium": round(_safe_float(r[4]) or 0, 2),
            })

        # By risk_category
        cat_sql = """
            SELECT
                risk_category,
                COUNT(*)                                                       AS total,
                COUNT(CASE WHEN decision = 'go' THEN 1 END)                   AS bound,
                ROUND(
                    COUNT(CASE WHEN decision = 'go' THEN 1 END) * 100.0
                    / NULLIF(COUNT(CASE WHEN decision IN ('go','no_go') THEN 1 END), 0),
                    2
                )                                                              AS win_rate_pct
            FROM assessments
            WHERE status NOT IN ('draft', 'cancelled', 'failed')
            GROUP BY risk_category
            ORDER BY total DESC
        """
        by_category = []
        for r in conn.execute(cat_sql).fetchall():
            by_category.append({
                "risk_category": r[0],
                "total": r[1],
                "bound": r[2],
                "win_rate_pct": _safe_float(r[3]) or 0.0,
            })

        # Monthly trend (last 12 months)
        monthly_sql = """
            SELECT
                DATE_TRUNC('month', created_at)                                AS month,
                COUNT(*)                                                        AS total,
                COUNT(CASE WHEN decision = 'go' THEN 1 END)                    AS bound,
                ROUND(
                    COUNT(CASE WHEN decision = 'go' THEN 1 END) * 100.0
                    / NULLIF(COUNT(CASE WHEN decision IN ('go','no_go') THEN 1 END), 0),
                    2
                )                                                               AS win_rate_pct,
                SUM(CASE WHEN decision = 'go' THEN premium ELSE 0 END)         AS bound_premium
            FROM assessments
            WHERE created_at >= (CURRENT_TIMESTAMP - INTERVAL '12 months')
              AND status NOT IN ('draft', 'cancelled', 'failed')
            GROUP BY 1
            ORDER BY 1
        """
        monthly_trend = []
        for r in conn.execute(monthly_sql).fetchall():
            monthly_trend.append({
                "month": str(r[0])[:7] if r[0] else None,
                "total": r[1],
                "bound": r[2],
                "win_rate_pct": _safe_float(r[3]) or 0.0,
                "bound_premium": round(_safe_float(r[4]) or 0, 2),
            })

        return {
            "overall": overall,
            "by_territory": by_territory,
            "by_risk_category": by_category,
            "monthly_trend": monthly_trend,
        }

    def _loss_ratios(
        self,
        conn: duckdb.DuckDBPyConnection,
        losses_df: pd.DataFrame,
    ) -> dict:
        """
        Loss ratio = Total incurred losses / Earned premium.

        Computed overall and by territory / risk category.
        Requires both assessments and losses tables to be registered.
        """
        if losses_df.empty:
            return {
                "overall": {"loss_ratio": None, "total_losses": 0.0, "earned_premium": 0.0},
                "by_territory": [],
                "by_risk_category": [],
                "note": "No loss data available yet",
            }

        # Register losses if not already done (idempotent since we pass conn)
        # Overall
        overall_sql = """
            SELECT
                SUM(l.loss_amount)                  AS total_losses,
                SUM(a.premium)                      AS earned_premium,
                CASE
                    WHEN SUM(a.premium) > 0
                    THEN ROUND(SUM(l.loss_amount) / SUM(a.premium), 4)
                    ELSE NULL
                END                                 AS loss_ratio
            FROM losses l
            JOIN assessments a ON a.id = l.assessment_id
            WHERE a.decision = 'go'
        """
        row = conn.execute(overall_sql).fetchone()
        overall = {
            "total_losses": round(_safe_float(row[0]) or 0, 2),
            "earned_premium": round(_safe_float(row[1]) or 0, 2),
            "loss_ratio": round(_safe_float(row[2]) or 0, 4) if row[2] else None,
            "loss_ratio_pct": round((_safe_float(row[2]) or 0) * 100, 2) if row[2] else None,
        }

        # By territory
        territory_sql = """
            SELECT
                a.territory,
                SUM(l.loss_amount)                  AS total_losses,
                SUM(a.premium)                      AS earned_premium,
                CASE
                    WHEN SUM(a.premium) > 0
                    THEN ROUND(SUM(l.loss_amount) / SUM(a.premium) * 100, 2)
                    ELSE NULL
                END                                 AS loss_ratio_pct
            FROM losses l
            JOIN assessments a ON a.id = l.assessment_id
            WHERE a.decision = 'go'
            GROUP BY a.territory
            ORDER BY total_losses DESC
        """
        by_territory = []
        for r in conn.execute(territory_sql).fetchall():
            by_territory.append({
                "territory": r[0],
                "total_losses": round(_safe_float(r[1]) or 0, 2),
                "earned_premium": round(_safe_float(r[2]) or 0, 2),
                "loss_ratio_pct": _safe_float(r[3]),
            })

        # By risk category
        cat_sql = """
            SELECT
                a.risk_category,
                SUM(l.loss_amount)                  AS total_losses,
                SUM(a.premium)                      AS earned_premium,
                CASE
                    WHEN SUM(a.premium) > 0
                    THEN ROUND(SUM(l.loss_amount) / SUM(a.premium) * 100, 2)
                    ELSE NULL
                END                                 AS loss_ratio_pct
            FROM losses l
            JOIN assessments a ON a.id = l.assessment_id
            WHERE a.decision = 'go'
            GROUP BY a.risk_category
            ORDER BY total_losses DESC
        """
        by_category = []
        for r in conn.execute(cat_sql).fetchall():
            by_category.append({
                "risk_category": r[0],
                "total_losses": round(_safe_float(r[1]) or 0, 2),
                "earned_premium": round(_safe_float(r[2]) or 0, 2),
                "loss_ratio_pct": _safe_float(r[3]),
            })

        return {
            "overall": overall,
            "by_territory": by_territory,
            "by_risk_category": by_category,
        }

    def _portfolio_kpis(self, conn: duckdb.DuckDBPyConnection) -> dict:
        """Top-level KPIs for CFO summary card."""
        sql = """
            SELECT
                COUNT(*)                                                AS total_assessments,
                COUNT(CASE WHEN status = 'completed' THEN 1 END)       AS completed,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END)     AS in_progress,
                COUNT(CASE WHEN decision = 'go' THEN 1 END)            AS bound,
                COUNT(CASE WHEN decision = 'no_go' THEN 1 END)         AS declined,
                COUNT(CASE WHEN decision = 'pending' THEN 1 END)       AS pending,
                SUM(premium)                                            AS total_premium,
                SUM(sum_insured)                                        AS total_tsi,
                AVG(risk_score)                                         AS avg_risk_score,
                COUNT(DISTINCT territory)                               AS territory_count,
                COUNT(DISTINCT risk_category)                           AS category_count,
                COUNT(DISTINCT broker_name)                             AS broker_count
            FROM assessments
        """
        row = conn.execute(sql).fetchone()
        cols = [
            "total_assessments", "completed", "in_progress", "bound", "declined",
            "pending", "total_premium", "total_tsi", "avg_risk_score",
            "territory_count", "category_count", "broker_count",
        ]
        kpis = dict(zip(cols, row))
        kpis["total_premium"] = round(_safe_float(kpis["total_premium"]) or 0, 2)
        kpis["total_tsi"] = round(_safe_float(kpis["total_tsi"]) or 0, 2)
        kpis["avg_risk_score"] = round(_safe_float(kpis["avg_risk_score"]) or 0, 1)

        win_rate = (kpis["bound"] / (kpis["bound"] + kpis["declined"])) * 100 if (kpis["bound"] + kpis["declined"]) > 0 else 0.0
        kpis["win_rate_pct"] = round(win_rate, 2)
        return kpis

    # ------------------------------------------------------------------
    # 4. Prophet forecasting
    # ------------------------------------------------------------------

    def _forecast_premium_trends(
        self,
        assessments_df: pd.DataFrame,
        periods: int = 12,
    ) -> dict:
        """
        Forecast monthly bound premium for the next `periods` months using Prophet.

        Falls back to a linear extrapolation if Prophet is unavailable or there
        is insufficient historical data (< 6 months).
        """
        try:
            from prophet import Prophet  # type: ignore
        except ImportError:
            logger.warning("Prophet not installed - using linear fallback for forecasting")
            return self._linear_forecast(assessments_df, periods)

        # Build monthly series of bound premium
        df = assessments_df.copy()
        df = df[df["decision"] == "go"].copy()
        df = df[df["created_at"].notna()].copy()

        if df.empty:
            return {"method": "prophet", "note": "No bound assessments for forecasting", "forecast": []}

        df["ds"] = df["created_at"].dt.to_period("M").dt.to_timestamp()
        monthly = df.groupby("ds")["premium"].sum().reset_index()
        monthly.columns = ["ds", "y"]
        monthly = monthly.sort_values("ds")

        if len(monthly) < 3:
            return self._linear_forecast(assessments_df, periods)

        try:
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                interval_width=0.80,
                changepoint_prior_scale=0.3,
            )
            model.fit(monthly)

            future = model.make_future_dataframe(periods=periods, freq="MS")
            forecast = model.predict(future)

            # Keep only future months
            last_actual = monthly["ds"].max()
            future_fc = forecast[forecast["ds"] > last_actual][
                ["ds", "yhat", "yhat_lower", "yhat_upper"]
            ].copy()
            future_fc["yhat"] = future_fc["yhat"].clip(lower=0)
            future_fc["yhat_lower"] = future_fc["yhat_lower"].clip(lower=0)
            future_fc["yhat_upper"] = future_fc["yhat_upper"].clip(lower=0)

            # Historical series for chart context
            historical = []
            for _, row in monthly.iterrows():
                historical.append({
                    "month": str(row["ds"])[:7],
                    "actual_premium": round(float(row["y"]), 2),
                })

            predictions = []
            for _, row in future_fc.iterrows():
                predictions.append({
                    "month": str(row["ds"])[:7],
                    "predicted_premium": round(float(row["yhat"]), 2),
                    "lower_bound": round(float(row["yhat_lower"]), 2),
                    "upper_bound": round(float(row["yhat_upper"]), 2),
                })

            total_predicted = round(sum(p["predicted_premium"] for p in predictions), 2)

            return {
                "method": "prophet",
                "horizon_months": periods,
                "total_predicted_premium": total_predicted,
                "avg_monthly_predicted": round(total_predicted / periods, 2) if periods else 0,
                "historical": historical,
                "forecast": predictions,
            }

        except Exception as exc:
            logger.warning("Prophet forecast failed: %s - using linear fallback", exc)
            return self._linear_forecast(assessments_df, periods)

    def _linear_forecast(
        self,
        assessments_df: pd.DataFrame,
        periods: int = 12,
    ) -> dict:
        """
        Simple linear extrapolation fallback for premium forecasting.
        Uses last 6 months average with month-over-month growth rate.
        """
        df = assessments_df[assessments_df["decision"] == "go"].copy()
        df = df[df["created_at"].notna()].copy()

        if df.empty:
            return {
                "method": "linear_fallback",
                "note": "Insufficient data for forecasting",
                "forecast": [],
            }

        df["month"] = df["created_at"].dt.to_period("M").dt.to_timestamp()
        monthly = df.groupby("month")["premium"].sum().reset_index()
        monthly = monthly.sort_values("month").tail(12)

        if len(monthly) < 2:
            avg = float(monthly["premium"].mean()) if len(monthly) == 1 else 0.0
            last_month = monthly["month"].iloc[-1] if not monthly.empty else datetime.now()
        else:
            avg = float(monthly["premium"].mean())
            growth = float(monthly["premium"].pct_change().mean()) or 0.0
            growth = max(min(growth, 0.20), -0.20)  # cap at ±20% MoM
            last_month = monthly["month"].iloc[-1]

            # Historical series
            historical = [
                {"month": str(row["month"])[:7], "actual_premium": round(float(row["premium"]), 2)}
                for _, row in monthly.iterrows()
            ]

            predictions = []
            current = avg
            for i in range(1, periods + 1):
                next_month = last_month + pd.DateOffset(months=i)
                current = current * (1 + growth)
                current = max(current, 0)
                predictions.append({
                    "month": str(next_month)[:7],
                    "predicted_premium": round(current, 2),
                    "lower_bound": round(current * 0.8, 2),
                    "upper_bound": round(current * 1.2, 2),
                })

            total_predicted = round(sum(p["predicted_premium"] for p in predictions), 2)
            return {
                "method": "linear_fallback",
                "horizon_months": periods,
                "total_predicted_premium": total_predicted,
                "avg_monthly_predicted": round(total_predicted / periods, 2) if periods else 0,
                "historical": historical,
                "forecast": predictions,
            }

        return {
            "method": "linear_fallback",
            "horizon_months": periods,
            "total_predicted_premium": 0.0,
            "avg_monthly_predicted": 0.0,
            "historical": [],
            "forecast": [],
        }

    # ------------------------------------------------------------------
    # 5. Public API methods
    # ------------------------------------------------------------------

    async def get_portfolio_dashboard(self, db: AsyncSession) -> dict:
        """
        Full CFO-grade dashboard combining all analytics.
        Returns a single JSON-serialisable dict.
        """
        assessments_df = await self._fetch_assessments(db)
        losses_df = await self._fetch_losses(db)

        if assessments_df.empty:
            return {
                "status": "no_data",
                "message": "No assessments found in portfolio",
                "kpis": {},
                "exposure_by_territory": [],
                "concentration_risk": {},
                "renewal_pipeline": {},
                "win_rates": {},
                "loss_ratios": {},
                "forecasts": {},
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        conn = self._duck_conn()
        self._register_frames(conn, assessments_df, losses_df)

        try:
            kpis = self._portfolio_kpis(conn)
            exposure = self._exposure_by_territory(conn)
            concentration = self._concentration_risk(conn)
            renewal = self._renewal_pipeline(conn)
            win_rates = self._win_rates(conn)
            loss_ratios = self._loss_ratios(conn, losses_df)
            forecasts = self._forecast_premium_trends(assessments_df)
        finally:
            conn.close()

        return {
            "status": "ok",
            "kpis": kpis,
            "exposure_by_territory": exposure,
            "concentration_risk": concentration,
            "renewal_pipeline": renewal,
            "win_rates": win_rates,
            "loss_ratios": loss_ratios,
            "forecasts": forecasts,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_exposure_by_territory(self, db: AsyncSession) -> dict:
        """Standalone endpoint: exposure aggregated by territory."""
        assessments_df = await self._fetch_assessments(db)
        losses_df = await self._fetch_losses(db)

        if assessments_df.empty:
            return {"territories": [], "total_assessments": 0, "total_premium": 0.0}

        conn = self._duck_conn()
        self._register_frames(conn, assessments_df, losses_df)
        try:
            data = self._exposure_by_territory(conn)
        finally:
            conn.close()

        return {
            "territories": data,
            "total_assessments": sum(t["assessment_count"] for t in data),
            "total_premium": round(sum(t["total_premium"] for t in data), 2),
            "total_tsi": round(sum(t["total_sum_insured"] for t in data), 2),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_concentration_risk(self, db: AsyncSession) -> dict:
        """Standalone endpoint: HHI concentration risk analysis."""
        assessments_df = await self._fetch_assessments(db)
        losses_df = await self._fetch_losses(db)

        if assessments_df.empty:
            return {"note": "No data available", "territory": {}, "risk_category": {}}

        conn = self._duck_conn()
        self._register_frames(conn, assessments_df, losses_df)
        try:
            data = self._concentration_risk(conn)
        finally:
            conn.close()

        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        return data

    async def get_renewal_pipeline(
        self, db: AsyncSession, horizon_days: int = 90
    ) -> dict:
        """Standalone endpoint: renewal pipeline within horizon_days."""
        assessments_df = await self._fetch_assessments(db)
        losses_df = await self._fetch_losses(db)

        if assessments_df.empty:
            return {"renewals": [], "total_renewals": 0, "total_premium_at_risk": 0.0}

        conn = self._duck_conn()
        self._register_frames(conn, assessments_df, losses_df)
        try:
            data = self._renewal_pipeline(conn, horizon_days)
        finally:
            conn.close()

        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        return data

    async def get_forecasts(
        self, db: AsyncSession, horizon_months: int = 12
    ) -> dict:
        """Standalone endpoint: Prophet/linear premium forecasts."""
        assessments_df = await self._fetch_assessments(db)

        if assessments_df.empty:
            return {"note": "No data available for forecasting", "forecast": []}

        data = self._forecast_premium_trends(assessments_df, periods=horizon_months)
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        return data


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

portfolio_analytics = PortfolioAnalyticsService()
