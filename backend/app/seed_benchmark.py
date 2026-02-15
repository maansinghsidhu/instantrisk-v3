"""
Seed benchmark loss run data for demo.

Generates realistic benchmark data for ClaimSense queries.
Runs automatically if benchmark_loss_runs table is empty.
"""
import random  # nosec B311 - used for non-security seed data generation
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.loss_run import BenchmarkLossRun


# Realistic parameters by policy type
POLICY_CONFIGS = {
    "GL": {
        "name": "General Liability",
        "claim_types": ["bodily_injury", "property_damage", "product_liability", "completed_operations", "personal_injury"],
        "avg_severity": 35000,
        "severity_std": 45000,
        "frequency_per_year": 8.5,
        "loss_ratio_mean": 0.62,
    },
    "WC": {
        "name": "Workers Compensation",
        "claim_types": ["medical", "indemnity", "permanent_disability", "temporary_disability", "fatality"],
        "avg_severity": 28000,
        "severity_std": 40000,
        "frequency_per_year": 12.0,
        "loss_ratio_mean": 0.68,
    },
    "AL": {
        "name": "Auto Liability",
        "claim_types": ["bodily_injury", "property_damage", "collision", "comprehensive", "uninsured_motorist"],
        "avg_severity": 22000,
        "severity_std": 30000,
        "frequency_per_year": 6.0,
        "loss_ratio_mean": 0.70,
    },
    "PR": {
        "name": "Property",
        "claim_types": ["fire", "water_damage", "wind_hail", "theft", "business_interruption", "equipment_breakdown"],
        "avg_severity": 55000,
        "severity_std": 80000,
        "frequency_per_year": 4.0,
        "loss_ratio_mean": 0.55,
    },
}

STATES = [
    "CA", "TX", "NY", "FL", "IL", "PA", "OH", "GA", "NC", "MI",
    "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI",
    "CO", "MN", "SC", "AL", "LA", "KY", "OR", "OK", "CT", "UT",
]

INDUSTRIES = [
    "Manufacturing", "Construction", "Retail Trade", "Healthcare",
    "Transportation", "Professional Services", "Hospitality",
    "Technology", "Real Estate", "Education",
]

YEARS = list(range(2015, 2025))


def _generate_claim(policy_type: str, state: str, industry: str, year: int) -> dict:
    """Generate a single realistic benchmark claim."""
    config = POLICY_CONFIGS[policy_type]

    claim_type = random.choice(config["claim_types"])

    # Generate severity with lognormal distribution (more realistic)
    severity = max(500, random.lognormvariate(10.0, 1.2))
    # Scale to match policy type
    severity = severity * (config["avg_severity"] / 25000)

    amount_paid = round(Decimal(str(severity * random.uniform(0.3, 1.0))), 2)
    amount_reserved = round(Decimal(str(severity * random.uniform(0.0, 0.5))), 2)
    amount_incurred = amount_paid + amount_reserved

    # Claim date within the policy year
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    claim_dt = date(year, month, day)

    loss_ratio = config["loss_ratio_mean"] + random.gauss(0, 0.15)
    loss_ratio = max(0.1, min(2.0, loss_ratio))

    freq = config["frequency_per_year"] + random.gauss(0, 2)
    freq = max(0.5, freq)

    return {
        "id": uuid.uuid4(),
        "policy_type": policy_type,
        "state": state,
        "industry": industry,
        "industry_code": str(random.randint(2000, 9000)),
        "policy_year": year,
        "claim_date": claim_dt,
        "report_date": date(year, min(month + random.randint(0, 2), 12), day),
        "claim_type": claim_type,
        "claim_description": f"{config['name']} claim - {claim_type.replace('_', ' ')}",
        "amount_paid": amount_paid,
        "amount_reserved": amount_reserved,
        "amount_incurred": amount_incurred,
        "deductible": Decimal(str(random.choice([1000, 2500, 5000, 10000, 25000]))),
        "loss_ratio": round(loss_ratio, 4),
        "claim_frequency": round(freq, 2),
        "severity": round(float(amount_incurred), 2),
        "source": "claimsense_benchmark",
        "created_at": datetime.utcnow(),
    }


async def seed_benchmark_data(session: AsyncSession) -> int:
    """
    Seed benchmark_loss_runs table with realistic demo data.

    Returns number of records inserted.
    """
    # Check if data already exists
    result = await session.execute(
        select(func.count()).select_from(BenchmarkLossRun)
    )
    count = result.scalar()
    if count and count > 0:
        return 0  # Already seeded

    records = []
    random.seed(42)  # Reproducible data

    for policy_type in POLICY_CONFIGS:
        config = POLICY_CONFIGS[policy_type]
        for state in STATES:
            for year in YEARS:
                # Number of claims varies by state size and policy type
                state_factor = 1.0
                if state in ("CA", "TX", "NY", "FL"):
                    state_factor = 1.5
                elif state in ("UT", "CT", "OK", "OR"):
                    state_factor = 0.6

                num_claims = max(1, int(
                    config["frequency_per_year"] * state_factor * random.uniform(0.5, 1.5)
                ))

                industry = random.choice(INDUSTRIES)
                for _ in range(num_claims):
                    records.append(_generate_claim(policy_type, state, industry, year))

    # Bulk insert
    batch_size = 500
    total = len(records)
    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        session.add_all([BenchmarkLossRun(**r) for r in batch])
        await session.flush()

    await session.commit()
    return total
