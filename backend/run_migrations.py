"""
Run Alembic migrations on RDS for god mode features.
Creates tables: assessment_vectors, risk_monitoring_alerts, global_events, etc.
"""

import os
import subprocess

# Database connection
os.environ['DATABASE_URL'] = 'postgresql://instantrisk_admin:W8xSpGuFkgiGGaIowLFYrNyy@instantrisk-db.cyjui2sqceiw.us-east-1.rds.amazonaws.com:5432/instantrisk'

print("="*80)
print("Running God Mode Database Migrations")
print("="*80)
print()

# Run migrations
print("Executing: alembic upgrade head")
print()

result = subprocess.run(
    ["alembic", "upgrade", "head"],
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

if result.returncode == 0:
    print()
    print("="*80)
    print("✓ MIGRATIONS COMPLETE")
    print("="*80)
    print()
    print("God mode tables created:")
    print("  - assessment_vectors (precedent search)")
    print("  - risk_monitoring_alerts (HIBP monitoring)")
    print("  - global_events (event intelligence)")
    print("  - Plus investigation/compliance tables")
    print()
    print("God mode platform is now FULLY OPERATIONAL!")
else:
    print()
    print("✗ MIGRATION FAILED")
    print(f"Exit code: {result.returncode}")
