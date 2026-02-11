"""
ClaimSense Data Ingestion Service

Fetches claims data from Parametriks ClaimSense Lambda API,
stores in local PostgreSQL, and indexes into Qdrant for RAG.

Gate 4 Enhancement: Redis caching for benchmark queries (24h TTL).
"""

import json
import logging
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
import redis.asyncio as aioredis

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.config import settings

logger = logging.getLogger(__name__)

# Redis client singleton for ClaimSense caching
_claimsense_redis: Optional[aioredis.Redis] = None
BENCHMARK_CACHE_TTL = 86400  # 24 hours


async def get_claimsense_redis() -> aioredis.Redis:
    """Get or create Redis client for ClaimSense caching."""
    global _claimsense_redis
    if _claimsense_redis is None:
        _claimsense_redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    return _claimsense_redis

CLAIMSENSE_API_URL = "https://vgyk08rvg4.execute-api.us-east-1.amazonaws.com/ucop-db-genai-insights-lambda"


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


class ClaimSenseService:
    """Service for fetching and managing ClaimSense claims data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def fetch_claims_from_api(self) -> List[Dict[str, Any]]:
        """Fetch raw claims data from ClaimSense Lambda API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(CLAIMSENSE_API_URL)

                if response.status_code != 200:
                    logger.error(f"ClaimSense API error: {response.status_code}")
                    return []

                data = response.json()

                # The Lambda returns {"statusCode": 200, "body": "..."}
                if isinstance(data, dict) and "body" in data:
                    body = data["body"]
                    if isinstance(body, str):
                        claims = json.loads(body)
                    else:
                        claims = body
                elif isinstance(data, list):
                    claims = data
                else:
                    claims = [data]

                logger.info(f"Fetched {len(claims)} claims from ClaimSense API")
                return claims

        except Exception as e:
            logger.error(f"Failed to fetch claims from ClaimSense: {e}")
            return []

    async def sync_claims_data(self) -> Dict[str, Any]:
        """
        Sync claims data from ClaimSense API to local storage.

        Returns sync statistics.
        """
        from app.models.claims import ClaimRecord, ClaimsSyncLog

        claims_data = await self.fetch_claims_from_api()
        if not claims_data:
            return {"status": "error", "message": "No data fetched from API", "count": 0}

        inserted = 0
        updated = 0
        errors = 0

        for claim in claims_data:
            try:
                # Extract fields from DynamoDB format (varies by dataset)
                claim_id = str(claim.get("id", claim.get("Claim_Number", claim.get("claim_id", ""))))
                if not claim_id:
                    continue

                # Check if exists
                existing = await self.db.execute(
                    select(ClaimRecord).where(ClaimRecord.claim_id == claim_id)
                )
                existing_record = existing.scalar_one_or_none()

                # Build record data
                record_data = {
                    "claim_id": claim_id,
                    "policyholder": str(claim.get("Policyholder", claim.get("policyholder", claim.get("Insured_Name", "")))),
                    "cause": str(claim.get("Cause_of_Incident", claim.get("cause", claim.get("Loss_Type", "")))),
                    "amount": self._parse_amount(claim.get("Total_Incurred", claim.get("amount", claim.get("Claim_Amount", 0)))),
                    "date_of_loss": str(claim.get("Date_of_Loss", claim.get("date", claim.get("Loss_Date", "")))),
                    "status": str(claim.get("Status", claim.get("status", ""))),
                    "line_of_business": str(claim.get("Line_of_Business", claim.get("Coverage", ""))),
                    "raw_data": json.loads(json.dumps(claim, cls=DecimalEncoder)),
                }

                if existing_record:
                    for key, value in record_data.items():
                        if key != "claim_id":
                            setattr(existing_record, key, value)
                    existing_record.updated_at = datetime.now(timezone.utc)
                    updated += 1
                else:
                    record = ClaimRecord(**record_data)
                    self.db.add(record)
                    inserted += 1

            except Exception as e:
                logger.error(f"Error processing claim: {e}")
                errors += 1

        try:
            await self.db.commit()
        except Exception as e:
            logger.error(f"Error committing claims: {e}")
            await self.db.rollback()
            return {"status": "error", "message": str(e), "count": 0}

        # Log sync
        sync_log = ClaimsSyncLog(
            records_fetched=len(claims_data),
            records_inserted=inserted,
            records_updated=updated,
            records_errors=errors,
            source_url=CLAIMSENSE_API_URL,
        )
        self.db.add(sync_log)
        await self.db.commit()

        # Index into Qdrant
        indexed = await self._index_claims_to_qdrant(claims_data)

        result = {
            "status": "success",
            "fetched": len(claims_data),
            "inserted": inserted,
            "updated": updated,
            "errors": errors,
            "indexed_to_qdrant": indexed,
        }
        logger.info(f"Claims sync complete: {result}")
        return result

    async def _index_claims_to_qdrant(self, claims_data: List[Dict]) -> int:
        """Index claims text into Qdrant for semantic search."""
        from app.services.rag_indexer import rag_indexer

        documents = []
        for claim in claims_data:
            # Build searchable text from claim fields
            parts = []
            for key, value in claim.items():
                if value and str(value).strip():
                    parts.append(f"{key}: {value}")
            text = "\n".join(parts)

            if len(text) > 20:
                documents.append({
                    "text": text,
                    "claim_id": str(claim.get("id", claim.get("Claim_Number", ""))),
                    "policyholder": str(claim.get("Policyholder", "")),
                    "cause": str(claim.get("Cause_of_Incident", "")),
                    "amount": str(claim.get("Total_Incurred", "")),
                })

        if documents:
            return rag_indexer.add_documents(documents, doc_type="claim")
        return 0

    def _parse_amount(self, value) -> float:
        """Parse claim amount from various formats."""
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0

    async def get_claims(
        self,
        limit: int = 100,
        offset: int = 0,
        cause: Optional[str] = None,
        policyholder: Optional[str] = None,
    ) -> List[Dict]:
        """Query local claims with optional filters."""
        from app.models.claims import ClaimRecord

        query = select(ClaimRecord)
        if cause:
            query = query.where(ClaimRecord.cause.ilike(f"%{cause}%"))
        if policyholder:
            query = query.where(ClaimRecord.policyholder.ilike(f"%{policyholder}%"))

        query = query.order_by(ClaimRecord.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        records = result.scalars().all()

        return [
            {
                "id": r.id,
                "claim_id": r.claim_id,
                "policyholder": r.policyholder,
                "cause": r.cause,
                "amount": r.amount,
                "date_of_loss": r.date_of_loss,
                "status": r.status,
                "line_of_business": r.line_of_business,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

    async def get_stats(self) -> Dict[str, Any]:
        """Get claims statistics."""
        from app.models.claims import ClaimRecord

        total = await self.db.execute(select(func.count(ClaimRecord.id)))
        total_count = total.scalar() or 0

        total_amount = await self.db.execute(select(func.sum(ClaimRecord.amount)))
        sum_amount = total_amount.scalar() or 0

        avg_amount = await self.db.execute(select(func.avg(ClaimRecord.amount)))
        average = avg_amount.scalar() or 0

        max_amount = await self.db.execute(select(func.max(ClaimRecord.amount)))
        highest = max_amount.scalar() or 0

        return {
            "total_claims": total_count,
            "total_amount": float(sum_amount),
            "average_amount": float(average),
            "highest_claim": float(highest),
        }

    # ===== Benchmark Query Methods (for ClaimSense router) =====

    async def query_benchmark(
        self,
        policy_type: str,
        state: Optional[str] = None,
        industry: Optional[str] = None,
        years: Optional[List[int]] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
    ) -> "BenchmarkResult":
        """Query benchmark loss run data with aggregations.

        Gate 4 Enhancement: Results are cached in Redis for 24 hours.
        """
        from app.models.loss_run import BenchmarkLossRun
        import statistics

        # Build cache key
        years_str = ",".join(map(str, sorted(years))) if years else ""
        cache_key = f"claimsense:benchmark:{policy_type}:{state or ''}:{industry or ''}:{years_str}:{min_year or ''}:{max_year or ''}"

        # Try to get from cache
        try:
            redis = await get_claimsense_redis()
            cached = await redis.get(cache_key)
            if cached:
                logger.debug(f"ClaimSense cache hit: {cache_key}")
                cached_data = json.loads(cached)
                return BenchmarkResult(
                    policy_type=policy_type,
                    state=state,
                    industry=industry,
                    years=cached_data.get("years", []),
                    data=cached_data.get("data", {}),
                )
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")

        query = select(BenchmarkLossRun).where(
            BenchmarkLossRun.policy_type == policy_type
        )
        if state:
            query = query.where(BenchmarkLossRun.state == state)
        if industry:
            query = query.where(BenchmarkLossRun.industry.ilike(f"%{industry}%"))
        if years:
            query = query.where(BenchmarkLossRun.policy_year.in_(years))
        if min_year:
            query = query.where(BenchmarkLossRun.policy_year >= min_year)
        if max_year:
            query = query.where(BenchmarkLossRun.policy_year <= max_year)

        result = await self.db.execute(query)
        claims = result.scalars().all()

        if not claims:
            return BenchmarkResult(
                policy_type=policy_type,
                state=state,
                industry=industry,
                years=[],
                data={},
            )

        amounts = [float(c.amount_paid or 0) + float(c.amount_reserved or 0) for c in claims]
        paid_amounts = [float(c.amount_paid or 0) for c in claims]
        reserved_amounts = [float(c.amount_reserved or 0) for c in claims]
        all_years = sorted(set(c.policy_year for c in claims if c.policy_year))

        # Claims by type
        by_type: Dict[str, Dict] = {}
        for c in claims:
            ct = c.claim_type or "Unknown"
            if ct not in by_type:
                by_type[ct] = {"count": 0, "total_paid": 0, "total_reserved": 0}
            by_type[ct]["count"] += 1
            by_type[ct]["total_paid"] += float(c.amount_paid or 0)
            by_type[ct]["total_reserved"] += float(c.amount_reserved or 0)

        # Claims by year
        by_year: Dict[str, Dict] = {}
        for c in claims:
            yr = str(c.policy_year) if c.policy_year else "Unknown"
            if yr not in by_year:
                by_year[yr] = {"count": 0, "total_paid": 0, "total_reserved": 0}
            by_year[yr]["count"] += 1
            by_year[yr]["total_paid"] += float(c.amount_paid or 0)
            by_year[yr]["total_reserved"] += float(c.amount_reserved or 0)

        sorted_amounts = sorted(amounts)
        n = len(sorted_amounts)

        data = {
            "total_claims": len(claims),
            "total_paid": sum(paid_amounts),
            "total_reserved": sum(reserved_amounts),
            "total_incurred": sum(amounts),
            "average_severity": statistics.mean(amounts) if amounts else 0,
            "median_severity": statistics.median(amounts) if amounts else 0,
            "percentiles": {
                "p25": sorted_amounts[n // 4] if n >= 4 else (sorted_amounts[0] if n else 0),
                "p50": sorted_amounts[n // 2] if n >= 2 else (sorted_amounts[0] if n else 0),
                "p75": sorted_amounts[3 * n // 4] if n >= 4 else (sorted_amounts[-1] if n else 0),
                "p90": sorted_amounts[int(n * 0.9)] if n >= 10 else (sorted_amounts[-1] if n else 0),
                "p95": sorted_amounts[int(n * 0.95)] if n >= 20 else (sorted_amounts[-1] if n else 0),
            },
            "claim_frequency_per_year": len(claims) / len(all_years) if all_years else 0,
            "claims_by_type": by_type,
            "claims_by_year": by_year,
            "years_of_data": len(all_years),
        }

        # Cache the result in Redis (24 hour TTL)
        try:
            redis = await get_claimsense_redis()
            cache_data = {"years": all_years, "data": data}
            await redis.setex(cache_key, BENCHMARK_CACHE_TTL, json.dumps(cache_data))
            logger.debug(f"ClaimSense cache set: {cache_key}")
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")

        return BenchmarkResult(
            policy_type=policy_type,
            state=state,
            industry=industry,
            years=all_years,
            data=data,
        )

    async def query_insured(self, assessment_id: str) -> Dict[str, Any]:
        """Query uploaded insured loss run data."""
        from app.models.loss_run import InsuredLossRun, ClaimStatus
        import statistics

        result = await self.db.execute(
            select(InsuredLossRun).where(InsuredLossRun.assessment_id == assessment_id)
        )
        claims = result.scalars().all()

        if not claims:
            return {"assessment_id": assessment_id, "total_claims": 0}

        amounts = [float(c.total_incurred) for c in claims]
        all_years = sorted(set(c.policy_year for c in claims if c.policy_year))

        open_claims = sum(1 for c in claims if c.status == ClaimStatus.OPEN)
        closed_claims = sum(1 for c in claims if c.status == ClaimStatus.CLOSED)

        by_type: Dict[str, Dict] = {}
        for c in claims:
            ct = c.claim_type or "Unknown"
            if ct not in by_type:
                by_type[ct] = {"count": 0, "total_paid": 0, "total_reserved": 0}
            by_type[ct]["count"] += 1
            by_type[ct]["total_paid"] += float(c.amount_paid or 0)
            by_type[ct]["total_reserved"] += float(c.amount_reserved or 0)

        return {
            "assessment_id": assessment_id,
            "total_claims": len(claims),
            "open_claims": open_claims,
            "closed_claims": closed_claims,
            "total_paid": sum(float(c.amount_paid or 0) for c in claims),
            "total_reserved": sum(float(c.amount_reserved or 0) for c in claims),
            "total_incurred": sum(amounts),
            "average_severity": statistics.mean(amounts) if amounts else 0,
            "median_severity": statistics.median(amounts) if amounts else 0,
            "largest_claim": max(amounts) if amounts else 0,
            "claim_frequency_per_year": len(claims) / len(all_years) if all_years else 0,
            "claims_by_type": by_type,
            "years_of_history": len(all_years),
            "years": all_years,
        }

    async def compare(
        self,
        assessment_id: str,
        policy_type: str,
        state: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> "ComparisonResult":
        """Compare insured loss history against benchmarks."""
        benchmark = await self.query_benchmark(policy_type, state, industry)
        insured = await self.query_insured(assessment_id)

        # Build comparison metrics
        metrics = {}
        b_data = benchmark.to_dict()
        if b_data.get("total_claims", 0) > 0 and insured.get("total_claims", 0) > 0:
            b_avg = b_data.get("average_severity", 0)
            i_avg = insured.get("average_severity", 0)
            metrics["severity_ratio"] = round(i_avg / b_avg, 2) if b_avg > 0 else 0
            metrics["frequency_ratio"] = round(
                insured.get("claim_frequency_per_year", 0) / b_data.get("claim_frequency_per_year", 1),
                2
            ) if b_data.get("claim_frequency_per_year", 0) > 0 else 0
            metrics["better_than_benchmark"] = metrics.get("severity_ratio", 1) < 1.0

        # Generate narrative
        narrative = self._generate_comparison_narrative(insured, b_data, metrics)

        return ComparisonResult(
            assessment_id=assessment_id,
            insured_summary=insured,
            benchmark_summary=b_data,
            narrative=narrative,
            metrics=metrics,
        )

    def _generate_comparison_narrative(
        self, insured: Dict, benchmark: Dict, metrics: Dict
    ) -> str:
        """Generate comparison narrative."""
        if not insured.get("total_claims") or not benchmark.get("total_claims"):
            return "Insufficient data for comparison."

        parts = []
        severity_ratio = metrics.get("severity_ratio", 0)
        if severity_ratio > 1.2:
            parts.append(
                f"The insured's average claim severity (${insured['average_severity']:,.0f}) "
                f"is {(severity_ratio - 1) * 100:.0f}% higher than the industry benchmark "
                f"(${benchmark['average_severity']:,.0f}), indicating elevated loss experience."
            )
        elif severity_ratio < 0.8:
            parts.append(
                f"The insured's average claim severity (${insured['average_severity']:,.0f}) "
                f"is {(1 - severity_ratio) * 100:.0f}% lower than the industry benchmark "
                f"(${benchmark['average_severity']:,.0f}), indicating favorable loss experience."
            )
        else:
            parts.append(
                f"The insured's average claim severity (${insured['average_severity']:,.0f}) "
                f"is broadly in line with the industry benchmark "
                f"(${benchmark['average_severity']:,.0f})."
            )

        freq_ratio = metrics.get("frequency_ratio", 0)
        if freq_ratio > 1.2:
            parts.append(
                f"Claim frequency ({insured['claim_frequency_per_year']:.1f}/year) "
                f"exceeds the benchmark ({benchmark['claim_frequency_per_year']:.1f}/year)."
            )
        elif freq_ratio < 0.8:
            parts.append(
                f"Claim frequency ({insured['claim_frequency_per_year']:.1f}/year) "
                f"is below the benchmark ({benchmark['claim_frequency_per_year']:.1f}/year)."
            )

        return " ".join(parts) if parts else "Comparison complete."

    async def nl_query(
        self, question: str, context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Process natural language query about claims data."""
        context = context or {}

        # Simple keyword-based routing
        q_lower = question.lower()

        if any(w in q_lower for w in ["benchmark", "industry", "average", "compare"]):
            pt = context.get("policy_type", "GL")
            st = context.get("state")
            result = await self.query_benchmark(policy_type=pt, state=st)
            return {
                "query_type": "benchmark",
                "parameters": {"policy_type": pt, "state": st},
                "result": result.to_dict(),
            }

        if any(w in q_lower for w in ["insured", "loss history", "uploaded"]):
            aid = context.get("assessment_id")
            if aid:
                result = await self.query_insured(aid)
                return {
                    "query_type": "insured",
                    "parameters": {"assessment_id": aid},
                    "result": result,
                }

        # Default: benchmark query
        pt = context.get("policy_type", "GL")
        result = await self.query_benchmark(policy_type=pt)
        return {
            "query_type": "benchmark",
            "parameters": {"policy_type": pt},
            "result": result.to_dict(),
        }


class BenchmarkResult:
    """Result container for benchmark queries."""

    def __init__(self, policy_type, state, industry, years, data):
        self.policy_type = policy_type
        self.state = state
        self.industry = industry
        self.years = years
        self._data = data

    def to_dict(self):
        return self._data


class ComparisonResult:
    """Result container for comparison queries."""

    def __init__(self, assessment_id, insured_summary, benchmark_summary, narrative, metrics):
        self.assessment_id = assessment_id
        self.insured_summary = insured_summary
        self.benchmark_summary = benchmark_summary
        self.narrative = narrative
        self.metrics = metrics


def get_claimsense_service(db: AsyncSession) -> ClaimSenseService:
    """Factory function for ClaimSense service."""
    return ClaimSenseService(db)
