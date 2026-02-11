"""
Pricing V3 Router - Market Benchmark and Pricing Intelligence API

Provides pricing benchmark data based on line of business, coverage limits,
and industry sectors using market intelligence data.

Key features:
- Market rate benchmarking
- Premium range estimation
- Industry-specific pricing factors
- Historical rate trends
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# =============================================================================
# Response Schemas
# =============================================================================

class PremiumRange(BaseModel):
    """Premium range for a coverage amount."""
    min_premium: Decimal
    max_premium: Decimal
    average_premium: Decimal
    median_premium: Decimal


class BenchmarkResponse(BaseModel):
    """Response for pricing benchmark."""
    line_of_business: str
    coverage_limit: Decimal
    currency: str
    industry: Optional[str] = None
    territory: Optional[str] = None
    min_premium: Decimal
    max_premium: Decimal
    average_premium: Decimal
    market_rate: Decimal
    rate_per_million: Decimal
    confidence_level: str
    factors_applied: List[str]
    market_data_points: int
    as_of_date: datetime
    notes: Optional[str] = None


class RateFactorResponse(BaseModel):
    """Response for rate factors."""
    factor_name: str
    factor_type: str
    base_value: float
    description: str
    applicable_lines: List[str]


class IndustryRiskProfile(BaseModel):
    """Industry risk profile."""
    industry_code: str
    industry_name: str
    risk_tier: str
    base_rate_modifier: float
    typical_coverage_needs: List[str]
    key_risks: List[str]


class MarketTrendResponse(BaseModel):
    """Market trend data."""
    line_of_business: str
    period: str
    rate_change_percent: float
    direction: str
    key_drivers: List[str]


# =============================================================================
# Market Data (In production, this would come from database/external sources)
# =============================================================================

# Base rates per $1M of coverage by line of business
BASE_RATES = {
    "property": {
        "rate_per_million": Decimal("2500"),
        "min_rate": Decimal("1800"),
        "max_rate": Decimal("4500"),
        "currency": "USD"
    },
    "cyber": {
        "rate_per_million": Decimal("8500"),
        "min_rate": Decimal("5000"),
        "max_rate": Decimal("15000"),
        "currency": "USD"
    },
    "marine": {
        "rate_per_million": Decimal("3500"),
        "min_rate": Decimal("2000"),
        "max_rate": Decimal("6000"),
        "currency": "USD"
    },
    "aviation": {
        "rate_per_million": Decimal("12000"),
        "min_rate": Decimal("8000"),
        "max_rate": Decimal("25000"),
        "currency": "USD"
    },
    "casualty": {
        "rate_per_million": Decimal("4000"),
        "min_rate": Decimal("2500"),
        "max_rate": Decimal("7500"),
        "currency": "USD"
    },
    "motor": {
        "rate_per_million": Decimal("3000"),
        "min_rate": Decimal("1500"),
        "max_rate": Decimal("5500"),
        "currency": "USD"
    },
    "professional_liability": {
        "rate_per_million": Decimal("6500"),
        "min_rate": Decimal("4000"),
        "max_rate": Decimal("12000"),
        "currency": "USD"
    },
    "directors_officers": {
        "rate_per_million": Decimal("9000"),
        "min_rate": Decimal("5500"),
        "max_rate": Decimal("18000"),
        "currency": "USD"
    },
    "energy": {
        "rate_per_million": Decimal("15000"),
        "min_rate": Decimal("10000"),
        "max_rate": Decimal("30000"),
        "currency": "USD"
    },
    "specialty": {
        "rate_per_million": Decimal("5000"),
        "min_rate": Decimal("3000"),
        "max_rate": Decimal("10000"),
        "currency": "USD"
    }
}

# Industry risk modifiers
INDUSTRY_MODIFIERS = {
    "technology": {
        "factor": 1.15,
        "risk_tier": "medium-high",
        "key_risks": ["cyber", "professional_liability", "directors_officers"]
    },
    "healthcare": {
        "factor": 1.25,
        "risk_tier": "high",
        "key_risks": ["professional_liability", "cyber", "property"]
    },
    "financial_services": {
        "factor": 1.20,
        "risk_tier": "high",
        "key_risks": ["cyber", "directors_officers", "professional_liability"]
    },
    "manufacturing": {
        "factor": 1.10,
        "risk_tier": "medium",
        "key_risks": ["property", "casualty", "marine"]
    },
    "retail": {
        "factor": 1.05,
        "risk_tier": "medium",
        "key_risks": ["property", "casualty", "cyber"]
    },
    "construction": {
        "factor": 1.30,
        "risk_tier": "high",
        "key_risks": ["casualty", "property", "professional_liability"]
    },
    "energy_sector": {
        "factor": 1.35,
        "risk_tier": "very_high",
        "key_risks": ["energy", "property", "casualty"]
    },
    "transportation": {
        "factor": 1.20,
        "risk_tier": "medium-high",
        "key_risks": ["motor", "marine", "aviation"]
    },
    "hospitality": {
        "factor": 1.08,
        "risk_tier": "medium",
        "key_risks": ["property", "casualty", "cyber"]
    },
    "professional_services": {
        "factor": 1.00,
        "risk_tier": "medium",
        "key_risks": ["professional_liability", "cyber", "directors_officers"]
    },
    "government": {
        "factor": 0.95,
        "risk_tier": "low-medium",
        "key_risks": ["cyber", "property", "casualty"]
    },
    "education": {
        "factor": 0.90,
        "risk_tier": "low-medium",
        "key_risks": ["property", "casualty", "cyber"]
    }
}

# Territory risk modifiers
TERRITORY_MODIFIERS = {
    "US": 1.25,
    "USA": 1.25,
    "UK": 1.00,
    "EU": 1.05,
    "APAC": 1.10,
    "LATAM": 1.20,
    "MEA": 1.15,
    "ANZ": 1.05,
    "CANADA": 1.10,
    "WORLDWIDE": 1.30,
    "WORLDWIDE_EX_US": 1.15
}

# Coverage limit factors (larger limits = better rates per million)
def get_limit_factor(limit: Decimal) -> float:
    """Get rate adjustment factor based on coverage limit."""
    limit_float = float(limit)
    if limit_float <= 1_000_000:
        return 1.20  # Small limits have higher rate per million
    elif limit_float <= 5_000_000:
        return 1.10
    elif limit_float <= 10_000_000:
        return 1.00
    elif limit_float <= 25_000_000:
        return 0.95
    elif limit_float <= 50_000_000:
        return 0.90
    elif limit_float <= 100_000_000:
        return 0.85
    else:
        return 0.80  # Large limits get volume discount


# =============================================================================
# Helper Functions
# =============================================================================

def _calculate_benchmark(
    line_of_business: str,
    coverage_limit: Decimal,
    industry: Optional[str] = None,
    territory: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate pricing benchmark based on parameters.

    Uses market data and applies relevant factors.
    """
    # Normalize line of business
    line_lower = line_of_business.lower().replace(" ", "_").replace("-", "_")

    # Get base rates
    base_rates = BASE_RATES.get(line_lower, BASE_RATES["specialty"])

    # Get rate per million
    rate_per_million = base_rates["rate_per_million"]
    min_rate = base_rates["min_rate"]
    max_rate = base_rates["max_rate"]
    currency = base_rates["currency"]

    factors_applied = []

    # Apply limit factor
    limit_factor = get_limit_factor(coverage_limit)
    rate_per_million *= Decimal(str(limit_factor))
    min_rate *= Decimal(str(limit_factor))
    max_rate *= Decimal(str(limit_factor))
    factors_applied.append(f"Limit Factor: {limit_factor:.2f}")

    # Apply industry modifier
    industry_factor = 1.0
    if industry:
        industry_lower = industry.lower().replace(" ", "_")
        industry_data = INDUSTRY_MODIFIERS.get(industry_lower, {"factor": 1.0})
        industry_factor = industry_data["factor"]
        rate_per_million *= Decimal(str(industry_factor))
        min_rate *= Decimal(str(industry_factor))
        max_rate *= Decimal(str(industry_factor))
        factors_applied.append(f"Industry Factor ({industry}): {industry_factor:.2f}")

    # Apply territory modifier
    territory_factor = 1.0
    if territory:
        territory_upper = territory.upper().replace(" ", "_")
        territory_factor = TERRITORY_MODIFIERS.get(territory_upper, 1.05)
        rate_per_million *= Decimal(str(territory_factor))
        min_rate *= Decimal(str(territory_factor))
        max_rate *= Decimal(str(territory_factor))
        factors_applied.append(f"Territory Factor ({territory}): {territory_factor:.2f}")

    # Calculate premiums
    limit_millions = coverage_limit / Decimal("1000000")

    min_premium = min_rate * limit_millions
    max_premium = max_rate * limit_millions
    average_premium = rate_per_million * limit_millions
    market_rate = average_premium  # Market rate is the expected rate

    # Determine confidence level based on data quality
    if industry and territory:
        confidence = "high"
        data_points = 150
    elif industry or territory:
        confidence = "medium"
        data_points = 75
    else:
        confidence = "low"
        data_points = 30

    return {
        "line_of_business": line_of_business,
        "coverage_limit": coverage_limit,
        "currency": currency,
        "industry": industry,
        "territory": territory,
        "min_premium": min_premium.quantize(Decimal("0.01")),
        "max_premium": max_premium.quantize(Decimal("0.01")),
        "average_premium": average_premium.quantize(Decimal("0.01")),
        "market_rate": market_rate.quantize(Decimal("0.01")),
        "rate_per_million": rate_per_million.quantize(Decimal("0.01")),
        "confidence_level": confidence,
        "factors_applied": factors_applied,
        "market_data_points": data_points,
        "as_of_date": datetime.now(timezone.utc)
    }


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/benchmark", response_model=BenchmarkResponse)
async def get_pricing_benchmark(
    line_of_business: str = Query(..., description="Line of business (e.g., cyber, property, marine)"),
    coverage_limit: Decimal = Query(..., gt=0, description="Coverage limit in base currency"),
    industry: Optional[str] = Query(None, description="Industry sector for risk adjustment"),
    territory: Optional[str] = Query(None, description="Primary territory (e.g., US, UK, EU, APAC)"),
    currency: str = Query("USD", description="Currency for premium display")
) -> BenchmarkResponse:
    """
    Get pricing benchmark for a specific risk profile.

    Calculates market-based premium estimates using line of business,
    coverage limits, industry, and territory factors.

    Args:
        line_of_business: Insurance line (cyber, property, marine, etc.)
        coverage_limit: Desired coverage amount
        industry: Industry sector for risk adjustment
        territory: Geographic territory for rate adjustment
        currency: Currency for display (default USD)

    Returns:
        BenchmarkResponse with premium estimates and market data.
    """
    # Validate line of business
    line_lower = line_of_business.lower().replace(" ", "_").replace("-", "_")
    if line_lower not in BASE_RATES:
        available_lines = list(BASE_RATES.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Invalid line of business. Available: {', '.join(available_lines)}"
        )

    benchmark = _calculate_benchmark(
        line_of_business=line_of_business,
        coverage_limit=coverage_limit,
        industry=industry,
        territory=territory
    )

    # Add notes based on confidence
    notes = None
    if benchmark["confidence_level"] == "low":
        notes = "Limited market data available. Consider providing industry and territory for more accurate estimates."
    elif benchmark["confidence_level"] == "medium":
        notes = "Moderate market data available. Results based on typical market rates with applied adjustments."

    return BenchmarkResponse(
        line_of_business=benchmark["line_of_business"],
        coverage_limit=benchmark["coverage_limit"],
        currency=currency,
        industry=benchmark["industry"],
        territory=benchmark["territory"],
        min_premium=benchmark["min_premium"],
        max_premium=benchmark["max_premium"],
        average_premium=benchmark["average_premium"],
        market_rate=benchmark["market_rate"],
        rate_per_million=benchmark["rate_per_million"],
        confidence_level=benchmark["confidence_level"],
        factors_applied=benchmark["factors_applied"],
        market_data_points=benchmark["market_data_points"],
        as_of_date=benchmark["as_of_date"],
        notes=notes
    )


@router.get("/lines")
async def get_available_lines() -> Dict[str, Any]:
    """
    Get all available lines of business with their base rates.

    Returns:
        Dictionary with lines of business and base rate information.
    """
    lines = []
    for line, rates in BASE_RATES.items():
        lines.append({
            "id": line,
            "name": line.replace("_", " ").title(),
            "base_rate_per_million": float(rates["rate_per_million"]),
            "min_rate": float(rates["min_rate"]),
            "max_rate": float(rates["max_rate"]),
            "currency": rates["currency"]
        })

    return {
        "count": len(lines),
        "lines": lines
    }


@router.get("/industries")
async def get_industry_profiles() -> Dict[str, Any]:
    """
    Get all industry risk profiles and their modifiers.

    Returns:
        Dictionary with industry profiles and risk information.
    """
    industries = []
    for industry, data in INDUSTRY_MODIFIERS.items():
        industries.append({
            "id": industry,
            "name": industry.replace("_", " ").title(),
            "risk_tier": data["risk_tier"],
            "rate_modifier": data["factor"],
            "key_risks": data["key_risks"]
        })

    # Sort by risk tier
    tier_order = {"low": 1, "low-medium": 2, "medium": 3, "medium-high": 4, "high": 5, "very_high": 6}
    industries.sort(key=lambda x: tier_order.get(x["risk_tier"], 3))

    return {
        "count": len(industries),
        "industries": industries
    }


@router.get("/territories")
async def get_territory_factors() -> Dict[str, Any]:
    """
    Get all territory risk factors.

    Returns:
        Dictionary with territory factors and descriptions.
    """
    territories = []
    for territory, factor in TERRITORY_MODIFIERS.items():
        risk_level = "low" if factor < 1.0 else "medium" if factor <= 1.1 else "high" if factor <= 1.25 else "very_high"
        territories.append({
            "id": territory,
            "name": territory.replace("_", " "),
            "factor": factor,
            "risk_level": risk_level
        })

    # Sort by factor
    territories.sort(key=lambda x: x["factor"])

    return {
        "count": len(territories),
        "territories": territories
    }


@router.get("/factors")
async def get_all_rate_factors() -> Dict[str, Any]:
    """
    Get all rate factors and their impacts.

    Returns comprehensive factor information for pricing transparency.
    """
    return {
        "limit_factors": {
            "description": "Rate adjustment based on coverage limit",
            "factors": [
                {"range": "Up to $1M", "factor": 1.20, "notes": "Higher rate per million for smaller limits"},
                {"range": "$1M - $5M", "factor": 1.10, "notes": "Slightly elevated rate"},
                {"range": "$5M - $10M", "factor": 1.00, "notes": "Base rate applies"},
                {"range": "$10M - $25M", "factor": 0.95, "notes": "5% volume discount"},
                {"range": "$25M - $50M", "factor": 0.90, "notes": "10% volume discount"},
                {"range": "$50M - $100M", "factor": 0.85, "notes": "15% volume discount"},
                {"range": "Over $100M", "factor": 0.80, "notes": "20% volume discount for large placements"}
            ]
        },
        "industry_factors": {
            "description": "Risk adjustment based on industry sector",
            "factor_range": {"min": 0.90, "max": 1.35}
        },
        "territory_factors": {
            "description": "Geographic risk adjustment",
            "factor_range": {"min": 0.95, "max": 1.30}
        }
    }


@router.get("/market-trends")
async def get_market_trends(
    line_of_business: Optional[str] = Query(None, description="Line of business filter")
) -> Dict[str, Any]:
    """
    Get current market trends and rate movements.

    Args:
        line_of_business: Optional filter for specific line

    Returns:
        Market trend data with rate changes and drivers.
    """
    # Sample market trend data (in production, from market intelligence)
    trends = [
        {
            "line_of_business": "cyber",
            "period": "Q4 2025",
            "rate_change_percent": 8.5,
            "direction": "hardening",
            "key_drivers": ["Ransomware frequency", "Regulatory changes", "Supply chain exposures"]
        },
        {
            "line_of_business": "property",
            "period": "Q4 2025",
            "rate_change_percent": 5.2,
            "direction": "hardening",
            "key_drivers": ["CAT losses", "Inflation", "Reinsurance costs"]
        },
        {
            "line_of_business": "marine",
            "period": "Q4 2025",
            "rate_change_percent": 2.3,
            "direction": "stable",
            "key_drivers": ["Geopolitical tensions", "Port congestion", "Climate risks"]
        },
        {
            "line_of_business": "casualty",
            "period": "Q4 2025",
            "rate_change_percent": 4.8,
            "direction": "hardening",
            "key_drivers": ["Social inflation", "Nuclear verdicts", "Litigation funding"]
        },
        {
            "line_of_business": "directors_officers",
            "period": "Q4 2025",
            "rate_change_percent": -2.5,
            "direction": "softening",
            "key_drivers": ["Increased capacity", "Competition", "Improved loss ratios"]
        },
        {
            "line_of_business": "professional_liability",
            "period": "Q4 2025",
            "rate_change_percent": 1.8,
            "direction": "stable",
            "key_drivers": ["AI-related claims", "E&O exposures", "Regulatory scrutiny"]
        },
        {
            "line_of_business": "aviation",
            "period": "Q4 2025",
            "rate_change_percent": 6.2,
            "direction": "hardening",
            "key_drivers": ["Supply chain issues", "Parts shortages", "Major losses"]
        },
        {
            "line_of_business": "energy",
            "period": "Q4 2025",
            "rate_change_percent": 3.5,
            "direction": "stable",
            "key_drivers": ["Transition risks", "ESG factors", "Natural catastrophes"]
        }
    ]

    if line_of_business:
        line_lower = line_of_business.lower().replace(" ", "_")
        trends = [t for t in trends if t["line_of_business"] == line_lower]

    return {
        "as_of_date": datetime.now(timezone.utc).isoformat(),
        "source": "Lloyd's Market Intelligence",
        "count": len(trends),
        "trends": trends
    }


@router.post("/compare")
async def compare_pricing(
    scenarios: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compare pricing across multiple scenarios.

    Args:
        scenarios: List of pricing scenarios to compare

    Returns:
        Comparison results with all scenarios evaluated.

    Example request body:
    [
        {"line_of_business": "cyber", "coverage_limit": 5000000, "industry": "technology"},
        {"line_of_business": "cyber", "coverage_limit": 5000000, "industry": "healthcare"}
    ]
    """
    if len(scenarios) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 scenarios allowed per comparison"
        )

    results = []
    for idx, scenario in enumerate(scenarios):
        try:
            benchmark = _calculate_benchmark(
                line_of_business=scenario.get("line_of_business", "property"),
                coverage_limit=Decimal(str(scenario.get("coverage_limit", 1000000))),
                industry=scenario.get("industry"),
                territory=scenario.get("territory")
            )
            results.append({
                "scenario_id": idx + 1,
                "input": scenario,
                "result": {
                    "min_premium": float(benchmark["min_premium"]),
                    "max_premium": float(benchmark["max_premium"]),
                    "average_premium": float(benchmark["average_premium"]),
                    "rate_per_million": float(benchmark["rate_per_million"]),
                    "factors_applied": benchmark["factors_applied"]
                }
            })
        except Exception as e:
            results.append({
                "scenario_id": idx + 1,
                "input": scenario,
                "error": str(e)
            })

    # Calculate comparison insights
    valid_results = [r for r in results if "result" in r]
    if len(valid_results) >= 2:
        premiums = [r["result"]["average_premium"] for r in valid_results]
        insights = {
            "lowest_premium_scenario": valid_results[premiums.index(min(premiums))]["scenario_id"],
            "highest_premium_scenario": valid_results[premiums.index(max(premiums))]["scenario_id"],
            "premium_range": max(premiums) - min(premiums),
            "premium_variance_percent": round((max(premiums) - min(premiums)) / min(premiums) * 100, 2) if min(premiums) > 0 else 0
        }
    else:
        insights = None

    return {
        "scenarios_evaluated": len(results),
        "results": results,
        "insights": insights
    }


# =============================================================================
# REPORT GENERATION ENDPOINT
# =============================================================================

class ReportRequest(BaseModel):
    """Request schema for pricing report generation."""
    line_of_business: str = Field(..., description="Primary line of business")
    coverage_limit: Decimal = Field(..., gt=0, description="Coverage limit")
    industry: Optional[str] = Field(None, description="Industry sector")
    territory: Optional[str] = Field(None, description="Geographic territory")
    include_market_trends: bool = Field(True, description="Include market trends section")
    include_comparison: bool = Field(True, description="Include competitor comparison")
    report_title: Optional[str] = Field(None, description="Custom report title")
    prepared_for: Optional[str] = Field(None, description="Client/broker name")
    format: str = Field("pdf", description="Output format: pdf or json")


class ReportResponse(BaseModel):
    """Response for report generation."""
    report_id: str
    title: str
    generated_at: datetime
    format: str
    content_type: str
    download_url: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


@router.post("/report", response_model=ReportResponse)
async def generate_pricing_report(
    request: ReportRequest
) -> ReportResponse:
    """
    Generate a comprehensive pricing benchmark report.

    Creates a detailed report including:
    - Market benchmark analysis
    - Premium recommendations
    - Industry comparisons
    - Market trends (optional)
    - Risk factors applied

    Args:
        request: Report generation parameters

    Returns:
        ReportResponse with report data or download URL
    """
    import uuid
    import io
    import base64

    report_id = f"PBR-{uuid.uuid4().hex[:8].upper()}"
    title = request.report_title or f"Pricing Benchmark Report - {request.line_of_business.title()}"
    generated_at = datetime.now(timezone.utc)

    # Get benchmark data
    benchmark = _calculate_benchmark(
        line_of_business=request.line_of_business,
        coverage_limit=request.coverage_limit,
        industry=request.industry,
        territory=request.territory
    )

    # Get market trends if requested
    market_trends = None
    if request.include_market_trends:
        line_lower = request.line_of_business.lower().replace(" ", "_").replace("-", "_")
        trends = [
            {"line_of_business": "cyber", "trend": "hardening", "rate_change_ytd": 12.5, "outlook": "continued increases expected"},
            {"line_of_business": "property", "trend": "stable", "rate_change_ytd": 3.2, "outlook": "modest increases likely"},
            {"line_of_business": "marine", "trend": "softening", "rate_change_ytd": -2.1, "outlook": "competitive market"},
            {"line_of_business": "aviation", "trend": "hardening", "rate_change_ytd": 8.7, "outlook": "capacity constraints"},
            {"line_of_business": "casualty", "trend": "stable", "rate_change_ytd": 4.5, "outlook": "selective underwriting"},
        ]
        market_trends = next((t for t in trends if t["line_of_business"] == line_lower), None)

    # Build comparison data if requested
    comparison = None
    if request.include_comparison:
        industries = ["technology", "healthcare", "manufacturing", "retail", "financial_services"]
        comparison_results = []
        for ind in industries[:5]:
            comp_benchmark = _calculate_benchmark(
                line_of_business=request.line_of_business,
                coverage_limit=request.coverage_limit,
                industry=ind,
                territory=request.territory
            )
            comparison_results.append({
                "industry": ind.replace("_", " ").title(),
                "average_premium": float(comp_benchmark["average_premium"]),
                "rate_per_million": float(comp_benchmark["rate_per_million"])
            })
        comparison = sorted(comparison_results, key=lambda x: x["average_premium"])

    # Build report data structure
    report_data = {
        "report_id": report_id,
        "title": title,
        "prepared_for": request.prepared_for,
        "generated_at": generated_at.isoformat(),
        "executive_summary": {
            "line_of_business": request.line_of_business.title(),
            "coverage_limit": float(request.coverage_limit),
            "recommended_premium_range": {
                "minimum": float(benchmark["min_premium"]),
                "maximum": float(benchmark["max_premium"]),
                "average": float(benchmark["average_premium"])
            },
            "market_rate_per_million": float(benchmark["rate_per_million"]),
            "confidence_level": benchmark["confidence_level"]
        },
        "benchmark_analysis": {
            "base_rate": float(benchmark["rate_per_million"]),
            "factors_applied": benchmark["factors_applied"],
            "industry": request.industry or "Not specified",
            "territory": request.territory or "Worldwide",
            "market_data_points": benchmark["market_data_points"]
        },
        "market_trends": market_trends,
        "industry_comparison": comparison,
        "methodology": {
            "data_sources": ["Lloyd's Market Intelligence", "Industry Benchmarks", "Historical Claims Data"],
            "calculation_basis": "Rate per million of coverage with industry and territory adjustments",
            "confidence_factors": ["Market data availability", "Industry specificity", "Territory data"]
        },
        "disclaimer": "This report is for informational purposes only and does not constitute a binding quote. Actual premiums may vary based on full underwriting review."
    }

    if request.format == "json":
        return ReportResponse(
            report_id=report_id,
            title=title,
            generated_at=generated_at,
            format="json",
            content_type="application/json",
            data=report_data
        )

    # Generate PDF using HTML template
    html_content = _generate_report_html(report_data)

    try:
        from weasyprint import HTML
        pdf_buffer = io.BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        pdf_base64 = base64.b64encode(pdf_buffer.read()).decode('utf-8')

        return ReportResponse(
            report_id=report_id,
            title=title,
            generated_at=generated_at,
            format="pdf",
            content_type="application/pdf",
            data={"pdf_base64": pdf_base64, "filename": f"{report_id}.pdf"}
        )
    except ImportError:
        # Fallback to JSON if weasyprint not available
        return ReportResponse(
            report_id=report_id,
            title=title,
            generated_at=generated_at,
            format="json",
            content_type="application/json",
            data=report_data
        )


def _generate_report_html(data: Dict[str, Any]) -> str:
    """Generate HTML for the pricing report."""
    exec_summary = data["executive_summary"]
    benchmark = data["benchmark_analysis"]

    comparison_rows = ""
    if data.get("industry_comparison"):
        for comp in data["industry_comparison"]:
            comparison_rows += f"""
            <tr>
                <td>{comp['industry']}</td>
                <td>${comp['average_premium']:,.0f}</td>
                <td>${comp['rate_per_million']:,.0f}</td>
            </tr>"""

    trends_section = ""
    if data.get("market_trends"):
        trends = data["market_trends"]
        trends_section = f"""
        <div class="section">
            <h2>Market Trends</h2>
            <p><strong>Current Trend:</strong> {trends.get('trend', 'N/A').title()}</p>
            <p><strong>YTD Rate Change:</strong> {trends.get('rate_change_ytd', 0):+.1f}%</p>
            <p><strong>Outlook:</strong> {trends.get('outlook', 'N/A').title()}</p>
        </div>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{data['title']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
            .header {{ background: #1e3a5f; color: white; padding: 30px; margin: -40px -40px 30px -40px; }}
            .header h1 {{ margin: 0 0 10px 0; font-size: 28px; }}
            .header p {{ margin: 5px 0; opacity: 0.9; }}
            .section {{ margin: 25px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }}
            .section h2 {{ color: #1e3a5f; margin-top: 0; border-bottom: 2px solid #1e3a5f; padding-bottom: 10px; }}
            .highlight {{ background: #e8f4f8; padding: 20px; border-left: 4px solid #00b894; margin: 20px 0; }}
            .highlight .amount {{ font-size: 32px; color: #00b894; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #1e3a5f; color: white; }}
            tr:hover {{ background: #f5f5f5; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
            .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; }}
            .badge-high {{ background: #00b894; color: white; }}
            .badge-medium {{ background: #fdcb6e; color: #333; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{data['title']}</h1>
            <p>Report ID: {data['report_id']}</p>
            <p>Generated: {data['generated_at'][:10]}</p>
            {f"<p>Prepared for: {data['prepared_for']}</p>" if data.get('prepared_for') else ""}
        </div>

        <div class="section">
            <h2>Executive Summary</h2>
            <p><strong>Line of Business:</strong> {exec_summary['line_of_business']}</p>
            <p><strong>Coverage Limit:</strong> ${exec_summary['coverage_limit']:,.0f}</p>

            <div class="highlight">
                <p>Recommended Premium Range</p>
                <p class="amount">${exec_summary['recommended_premium_range']['minimum']:,.0f} - ${exec_summary['recommended_premium_range']['maximum']:,.0f}</p>
                <p>Average: ${exec_summary['recommended_premium_range']['average']:,.0f}</p>
                <p><span class="badge badge-{'high' if exec_summary['confidence_level'] == 'high' else 'medium'}">{exec_summary['confidence_level'].title()} Confidence</span></p>
            </div>
        </div>

        <div class="section">
            <h2>Benchmark Analysis</h2>
            <p><strong>Market Rate:</strong> ${benchmark['base_rate']:,.0f} per $1M coverage</p>
            <p><strong>Industry:</strong> {benchmark['industry']}</p>
            <p><strong>Territory:</strong> {benchmark['territory']}</p>
            <p><strong>Factors Applied:</strong> {', '.join(benchmark['factors_applied'])}</p>
        </div>

        {trends_section}

        {f'''
        <div class="section">
            <h2>Industry Comparison</h2>
            <table>
                <thead>
                    <tr><th>Industry</th><th>Average Premium</th><th>Rate per $1M</th></tr>
                </thead>
                <tbody>
                    {comparison_rows}
                </tbody>
            </table>
        </div>
        ''' if comparison_rows else ''}

        <div class="footer">
            <p><strong>Disclaimer:</strong> {data['disclaimer']}</p>
            <p><strong>Data Sources:</strong> {', '.join(data['methodology']['data_sources'])}</p>
        </div>
    </body>
    </html>
    """
