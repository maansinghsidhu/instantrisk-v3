#!/usr/bin/env python3
"""
Seed ClaimSense Benchmark Loss Run Data into PostgreSQL (RDS)

Generates ~5000 realistic BenchmarkLossRun records and inserts them
directly into the benchmark_loss_runs table using psycopg2.

Covers:
  - Policy types: GL, WC, AL, PR
  - States: CA, TX, NY, FL, IL, PA, OH, GA, NC, NJ
  - Years: 2020-2025
  - Realistic severity distributions per policy type
  - NAICS industry codes with matching industry names
  - Varied claim frequencies by state and policy type

Usage:
    # With env var:
    export POSTGRES_PASSWORD=your_password
    python scripts/seed_claimsense_data.py

    # Or pass directly:
    POSTGRES_PASSWORD=your_password python scripts/seed_claimsense_data.py

Idempotent: uses INSERT ... ON CONFLICT DO NOTHING on primary key.
"""

import os
import sys
import uuid
import math
import random
from datetime import date, datetime
from decimal import Decimal

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Database connection settings
# ---------------------------------------------------------------------------
DB_HOST = os.environ.get(
    "POSTGRES_HOST",
    "instantrisk-db.cyjui2sqceiw.us-east-1.rds.amazonaws.com",
)
DB_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
DB_NAME = os.environ.get("POSTGRES_DB", "instantrisk")
DB_USER = os.environ.get("POSTGRES_USER", "instantrisk_admin")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")


def get_password() -> str:
    """Resolve database password from env var or AWS Secrets Manager."""
    if DB_PASSWORD:
        return DB_PASSWORD

    # Attempt AWS Secrets Manager lookup
    try:
        import boto3
        import json

        client = boto3.client("secretsmanager", region_name="us-east-1")
        secret = client.get_secret_value(SecretId="instantrisk/rds/admin")
        secret_dict = json.loads(secret["SecretString"])
        pw = secret_dict.get("password", "")
        if pw:
            print("[INFO] Retrieved password from AWS Secrets Manager")
            return pw
    except Exception as exc:
        print(f"[WARN] AWS Secrets Manager lookup failed: {exc}")

    print(
        "ERROR: No database password found.\n"
        "Set POSTGRES_PASSWORD env var or configure AWS credentials for Secrets Manager."
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Realistic data configuration
# ---------------------------------------------------------------------------

POLICY_TYPES = ["GL", "WC", "AL", "PR"]

STATES = ["CA", "TX", "NY", "FL", "IL", "PA", "OH", "GA", "NC", "NJ"]

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]

# NAICS industry codes mapped to industry names
INDUSTRY_MAP = {
    "541511": "Custom Computer Programming",
    "236220": "Commercial Building Construction",
    "722511": "Full-Service Restaurants",
    "311811": "Retail Bakeries",
    "441110": "New Car Dealers",
    "621111": "Physician Offices",
    "561720": "Janitorial Services",
    "238220": "Plumbing & HVAC Contractors",
    "484110": "General Freight Trucking",
    "721110": "Hotels & Motels",
    "531210": "Real Estate Agencies",
    "611310": "Colleges & Universities",
    "524210": "Insurance Agencies",
    "423510": "Metal Service Centers",
    "238910": "Site Preparation Contractors",
}

INDUSTRY_CODES = list(INDUSTRY_MAP.keys())

# State population weighting factors (relative claim volume)
STATE_FACTORS = {
    "CA": 1.8,
    "TX": 1.6,
    "NY": 1.5,
    "FL": 1.5,
    "IL": 1.2,
    "PA": 1.1,
    "OH": 1.0,
    "GA": 1.0,
    "NC": 0.9,
    "NJ": 0.9,
}

# Policy type severity and frequency parameters
# Severity is generated using a lognormal distribution.
# We parameterise via (target_mean, target_min, target_max).
POLICY_CONFIGS = {
    "GL": {
        "name": "General Liability",
        "claim_types": [
            "bodily_injury",
            "property_damage",
            "product_liability",
            "completed_operations",
            "personal_injury",
        ],
        # Target: avg ~$47K, range $5K-$500K
        "log_mu": 10.30,    # Tuned for ~$47K avg after clamping
        "log_sigma": 0.95,
        "sev_min": 5000,
        "sev_max": 500000,
        "base_freq": 5.5,   # claims per state-year (before state factor)
        "loss_ratio_mean": 0.62,
        "loss_ratio_std": 0.12,
        "freq_per_million": 4.2,
    },
    "WC": {
        "name": "Workers Compensation",
        "claim_types": [
            "medical",
            "indemnity",
            "permanent_disability",
            "temporary_disability",
            "fatality",
        ],
        # Target: avg ~$35K, range $2K-$250K
        "log_mu": 10.17,
        "log_sigma": 0.90,
        "sev_min": 2000,
        "sev_max": 250000,
        "base_freq": 7.0,
        "loss_ratio_mean": 0.68,
        "loss_ratio_std": 0.13,
        "freq_per_million": 5.8,
    },
    "AL": {
        "name": "Auto Liability",
        "claim_types": [
            "bodily_injury",
            "property_damage",
            "collision",
            "comprehensive",
            "uninsured_motorist",
        ],
        # Target: avg ~$28K, range $3K-$200K
        "log_mu": 9.95,
        "log_sigma": 0.85,
        "sev_min": 3000,
        "sev_max": 200000,
        "base_freq": 5.0,
        "loss_ratio_mean": 0.70,
        "loss_ratio_std": 0.14,
        "freq_per_million": 3.5,
    },
    "PR": {
        "name": "Property",
        "claim_types": [
            "fire",
            "water_damage",
            "wind_hail",
            "theft",
            "business_interruption",
            "equipment_breakdown",
        ],
        # Target: avg ~$125K, range $10K-$2M
        "log_mu": 11.30,
        "log_sigma": 1.05,
        "sev_min": 10000,
        "sev_max": 2000000,
        "base_freq": 3.0,
        "loss_ratio_mean": 0.55,
        "loss_ratio_std": 0.15,
        "freq_per_million": 2.1,
    },
}

# Claim type descriptions for realistic claim_description values
CLAIM_DESCRIPTIONS = {
    "bodily_injury": [
        "Slip and fall on premises",
        "Customer injury from falling merchandise",
        "Visitor tripped on uneven walkway",
        "Third-party injury during operations",
        "Pedestrian struck in parking area",
    ],
    "property_damage": [
        "Contractor damaged adjacent property",
        "Water leak from operations affected neighbor",
        "Equipment caused property damage during delivery",
        "Vehicle backed into client property",
        "Construction debris damaged adjacent building",
    ],
    "product_liability": [
        "Product malfunction caused injury",
        "Defective component failure",
        "Consumer allergic reaction to product",
        "Product recall related claim",
        "Manufacturing defect injury",
    ],
    "completed_operations": [
        "Post-completion structural issue",
        "Plumbing failure after project handoff",
        "HVAC installation caused water damage",
        "Electrical work led to fire post-completion",
        "Foundation crack discovered after construction",
    ],
    "personal_injury": [
        "Wrongful eviction claim",
        "Defamation suit from competitor",
        "Invasion of privacy claim",
        "False arrest allegation",
        "Malicious prosecution defense",
    ],
    "medical": [
        "On-the-job back injury treatment",
        "Repetitive stress injury therapy",
        "Emergency room visit after workplace fall",
        "Occupational disease treatment",
        "Surgical procedure for work injury",
    ],
    "indemnity": [
        "Lost wages during recovery",
        "Temporary total disability payments",
        "Wage replacement for injured worker",
        "Income benefits during rehabilitation",
        "Partial disability indemnity",
    ],
    "permanent_disability": [
        "Permanent partial disability settlement",
        "Loss of use of limb",
        "Permanent impairment rating",
        "Scheduled loss settlement",
        "Whole person impairment award",
    ],
    "temporary_disability": [
        "Temporary total disability benefits",
        "Short-term disability payments",
        "Recovery period wage replacement",
        "Light duty transition benefits",
        "Temporary partial disability",
    ],
    "fatality": [
        "Workplace fatality death benefit",
        "Fatal accident survivor benefits",
        "Death claim from industrial accident",
        "Occupational exposure fatality",
        "Construction site fatality",
    ],
    "collision": [
        "Fleet vehicle rear-end collision",
        "Multi-vehicle accident on highway",
        "Intersection collision with third party",
        "Delivery vehicle accident",
        "Company car collision during business use",
    ],
    "comprehensive": [
        "Hail damage to fleet vehicles",
        "Vehicle vandalism in company lot",
        "Flood damage to parked fleet",
        "Windshield replacement from road debris",
        "Animal collision on rural route",
    ],
    "uninsured_motorist": [
        "Hit-and-run damage to company vehicle",
        "Collision with uninsured driver",
        "Employee injured by uninsured motorist",
        "Underinsured motorist supplemental claim",
        "Phantom vehicle incident",
    ],
    "fire": [
        "Electrical fire in warehouse",
        "Kitchen fire in commercial space",
        "Arson damage to retail location",
        "Wildfire damage to property",
        "Heating system malfunction fire",
    ],
    "water_damage": [
        "Burst pipe in office building",
        "Roof leak caused inventory damage",
        "Sprinkler system malfunction",
        "Flooding from storm surge",
        "Sewage backup in basement",
    ],
    "wind_hail": [
        "Hurricane wind damage to roof",
        "Hailstorm damaged exterior cladding",
        "Tornado damage to outbuildings",
        "Severe storm blew off signage",
        "Wind-driven rain interior damage",
    ],
    "theft": [
        "Break-in and equipment theft",
        "Employee theft of inventory",
        "Copper wire theft from construction site",
        "Vehicle theft from company lot",
        "Burglary of electronics and tools",
    ],
    "business_interruption": [
        "Revenue loss from fire closure",
        "Business interruption from flood",
        "Income loss during building repair",
        "Supply chain disruption claim",
        "Utility outage production loss",
    ],
    "equipment_breakdown": [
        "HVAC compressor failure",
        "Electrical transformer burnout",
        "Boiler explosion damage",
        "Refrigeration system breakdown",
        "Production machinery failure",
    ],
}


# ---------------------------------------------------------------------------
# Data generation functions
# ---------------------------------------------------------------------------

def generate_severity(config: dict) -> float:
    """Generate a realistic claim severity using lognormal distribution."""
    raw = random.lognormvariate(config["log_mu"], config["log_sigma"])
    # Clamp to realistic range
    clamped = max(config["sev_min"], min(config["sev_max"], raw))
    return round(clamped, 2)


def generate_claim(
    policy_type: str, state: str, year: int, config: dict
) -> dict:
    """Generate a single benchmark loss run record."""
    # Pick an industry
    industry_code = random.choice(INDUSTRY_CODES)
    industry_name = INDUSTRY_MAP[industry_code]

    # Claim type and description
    claim_type = random.choice(config["claim_types"])
    descriptions = CLAIM_DESCRIPTIONS.get(claim_type, [f"{claim_type} claim"])
    claim_description = random.choice(descriptions)

    # Severity
    severity = generate_severity(config)

    # Split into paid vs reserved (older claims more paid, newer more reserved)
    year_age = 2025 - year  # 0 for 2025, 5 for 2020
    paid_ratio = min(0.95, 0.50 + year_age * 0.09 + random.uniform(-0.10, 0.10))
    paid_ratio = max(0.20, paid_ratio)

    amount_paid = round(severity * paid_ratio, 2)
    amount_reserved = round(severity * (1.0 - paid_ratio), 2)
    amount_incurred = round(amount_paid + amount_reserved, 2)

    # Claim date within the policy year
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    claim_dt = date(year, month, day)

    # Report date: 0-90 days after claim date
    report_lag_days = random.randint(0, 90)
    report_month = month + (report_lag_days // 30)
    report_year = year
    if report_month > 12:
        report_month -= 12
        report_year += 1
        if report_year > 2025:
            report_year = 2025
            report_month = 12
    report_day = min(day + (report_lag_days % 28), 28)
    report_dt = date(report_year, report_month, report_day)

    # Loss ratio with some noise
    loss_ratio = config["loss_ratio_mean"] + random.gauss(0, config["loss_ratio_std"])
    loss_ratio = round(max(0.10, min(2.0, loss_ratio)), 4)

    # Claim frequency (per $1M exposure)
    freq = config["freq_per_million"] + random.gauss(0, 1.0)
    freq = round(max(0.5, freq), 2)

    # Deductible
    deductible = Decimal(str(random.choice([1000, 2500, 5000, 10000, 25000, 50000])))

    return {
        "id": str(uuid.uuid4()),
        "policy_type": policy_type,
        "state": state,
        "industry": industry_name,
        "industry_code": industry_code,
        "policy_year": year,
        "claim_date": claim_dt,
        "report_date": report_dt,
        "claim_type": claim_type,
        "claim_description": claim_description,
        "amount_paid": Decimal(str(amount_paid)),
        "amount_reserved": Decimal(str(amount_reserved)),
        "amount_incurred": Decimal(str(amount_incurred)),
        "deductible": deductible,
        "loss_ratio": loss_ratio,
        "claim_frequency": freq,
        "severity": round(float(amount_incurred), 2),
        "source": "claimsense_benchmark",
        "created_at": datetime.utcnow(),
    }


def generate_all_records(target_count: int = 5000) -> list:
    """
    Generate ~target_count realistic BenchmarkLossRun records.

    Distributes claims across policy types, states, and years with
    realistic weighting.
    """
    random.seed(42)  # Reproducible generation

    # Calculate total weight to distribute target_count records
    total_weight = 0.0
    combos = []
    for pt in POLICY_TYPES:
        config = POLICY_CONFIGS[pt]
        for st in STATES:
            for yr in YEARS:
                weight = config["base_freq"] * STATE_FACTORS[st]
                combos.append((pt, st, yr, weight))
                total_weight += weight

    # Scale weights so total claims ~ target_count
    scale = target_count / total_weight

    records = []
    for pt, st, yr, weight in combos:
        config = POLICY_CONFIGS[pt]
        num_claims = max(1, int(round(weight * scale * random.uniform(0.7, 1.3))))
        for _ in range(num_claims):
            records.append(generate_claim(pt, st, yr, config))

    return records


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

INSERT_SQL = """
INSERT INTO benchmark_loss_runs (
    id,
    policy_type,
    state,
    industry,
    industry_code,
    policy_year,
    claim_date,
    report_date,
    claim_type,
    claim_description,
    amount_paid,
    amount_reserved,
    amount_incurred,
    deductible,
    loss_ratio,
    claim_frequency,
    severity,
    source,
    created_at
) VALUES (
    %(id)s,
    %(policy_type)s,
    %(state)s,
    %(industry)s,
    %(industry_code)s,
    %(policy_year)s,
    %(claim_date)s,
    %(report_date)s,
    %(claim_type)s,
    %(claim_description)s,
    %(amount_paid)s,
    %(amount_reserved)s,
    %(amount_incurred)s,
    %(deductible)s,
    %(loss_ratio)s,
    %(claim_frequency)s,
    %(severity)s,
    %(source)s,
    %(created_at)s
)
ON CONFLICT (id) DO NOTHING
"""


def seed_data():
    """Main entry point: generate records and insert into PostgreSQL."""
    password = get_password()

    print("=" * 60)
    print("ClaimSense Benchmark Data Seeder")
    print("=" * 60)
    print(f"  Host:     {DB_HOST}")
    print(f"  Port:     {DB_PORT}")
    print(f"  Database: {DB_NAME}")
    print(f"  User:     {DB_USER}")
    print()

    # Connect to PostgreSQL
    print("[1/4] Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=password,
            connect_timeout=15,
            sslmode="require",
        )
        conn.autocommit = False
        print("  Connected successfully.")
    except Exception as exc:
        print(f"  ERROR: Connection failed: {exc}")
        sys.exit(1)

    cur = conn.cursor()

    # Check existing record count
    try:
        cur.execute("SELECT COUNT(*) FROM benchmark_loss_runs")
        existing_count = cur.fetchone()[0]
        print(f"  Existing records in benchmark_loss_runs: {existing_count}")
    except Exception as exc:
        print(f"  WARNING: Could not count existing records: {exc}")
        conn.rollback()
        existing_count = 0

    # Generate records
    print("\n[2/4] Generating benchmark loss run records...")
    records = generate_all_records(target_count=5000)
    print(f"  Generated {len(records)} records")

    # Print distribution summary
    by_policy = {}
    by_state = {}
    by_year = {}
    total_severity = 0.0
    for r in records:
        pt = r["policy_type"]
        st = r["state"]
        yr = r["policy_year"]
        by_policy[pt] = by_policy.get(pt, 0) + 1
        by_state[st] = by_state.get(st, 0) + 1
        by_year[yr] = by_year.get(yr, 0) + 1
        total_severity += r["severity"]

    print("\n  Distribution by policy type:")
    for pt in sorted(by_policy.keys()):
        count = by_policy[pt]
        avg_sev = sum(
            r["severity"] for r in records if r["policy_type"] == pt
        ) / count
        print(f"    {pt}: {count:>5} records  (avg severity: ${avg_sev:>12,.2f})")

    print("\n  Distribution by state:")
    for st in sorted(by_state.keys()):
        print(f"    {st}: {by_state[st]:>5} records")

    print("\n  Distribution by year:")
    for yr in sorted(by_year.keys()):
        print(f"    {yr}: {by_year[yr]:>5} records")

    print(f"\n  Overall average severity: ${total_severity / len(records):,.2f}")

    # Insert in batches
    print("\n[3/4] Inserting records into benchmark_loss_runs...")
    batch_size = 500
    inserted = 0
    errors = 0

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        try:
            psycopg2.extras.execute_batch(cur, INSERT_SQL, batch, page_size=100)
            conn.commit()
            inserted += len(batch)
            pct = (inserted / len(records)) * 100
            print(f"  Inserted batch {i // batch_size + 1}: "
                  f"{inserted}/{len(records)} ({pct:.0f}%)")
        except Exception as exc:
            conn.rollback()
            errors += len(batch)
            print(f"  ERROR in batch {i // batch_size + 1}: {exc}")

    # Final count
    print("\n[4/4] Verifying final record count...")
    try:
        cur.execute("SELECT COUNT(*) FROM benchmark_loss_runs")
        final_count = cur.fetchone()[0]
    except Exception as exc:
        print(f"  WARNING: Could not verify count: {exc}")
        final_count = "unknown"

    # Summary by policy type from DB
    try:
        cur.execute("""
            SELECT
                policy_type,
                COUNT(*) as cnt,
                ROUND(AVG(severity)::numeric, 2) as avg_sev,
                MIN(policy_year) as min_yr,
                MAX(policy_year) as max_yr
            FROM benchmark_loss_runs
            GROUP BY policy_type
            ORDER BY policy_type
        """)
        db_summary = cur.fetchall()
    except Exception:
        db_summary = []

    cur.close()
    conn.close()

    # Print final summary
    print("\n" + "=" * 60)
    print("SEED COMPLETE")
    print("=" * 60)
    print(f"  Records generated:  {len(records)}")
    print(f"  Records inserted:   {inserted}")
    print(f"  Errors:             {errors}")
    print(f"  Total in table:     {final_count}")

    if db_summary:
        print("\n  Database summary by policy type:")
        print(f"  {'Type':<6} {'Count':>7} {'Avg Severity':>14} {'Years':>12}")
        print(f"  {'-'*6} {'-'*7} {'-'*14} {'-'*12}")
        for row in db_summary:
            pt, cnt, avg_sev, min_yr, max_yr = row
            print(f"  {pt:<6} {cnt:>7} ${float(avg_sev):>12,.2f} {min_yr}-{max_yr}")

    print()
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(seed_data())
