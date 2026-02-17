"""
Test script for Autonomous Investigation Agent

This script demonstrates how to use the autonomous investigation API endpoints.

Usage:
    python test_autonomous_investigation.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.autonomous_investigator import (
    run_autonomous_investigation,
    fetch_sec_edgar_data,
    fetch_osha_violations,
    fetch_epa_violations,
    fetch_news_reputation,
    check_hibp_breaches,
    check_cve_database
)


async def test_individual_agents():
    """Test each agent individually."""
    print("=" * 80)
    print("TESTING INDIVIDUAL AGENTS")
    print("=" * 80)

    test_company = "Microsoft Corporation"

    # Test Financial Agent
    print("\n[1/6] Testing Financial Agent (SEC EDGAR)...")
    financial_data = await fetch_sec_edgar_data(test_company)
    print(f"✓ Financial Agent: Found CIK {financial_data.get('cik', 'N/A')}")
    print(f"  Industry: {financial_data.get('sic_description', 'Unknown')}")
    print(f"  Filings: {len(financial_data.get('recent_10k_filings', []))} recent 10-K/10-Q")

    # Test Regulatory Agent - OSHA
    print("\n[2/6] Testing Regulatory Agent - OSHA...")
    osha_data = await fetch_osha_violations(test_company)
    print(f"✓ OSHA: Violations found: {osha_data.get('violations_found', False)}")
    print(f"  Total: {osha_data.get('total_violations', 0)}")

    # Test Regulatory Agent - EPA
    print("\n[3/6] Testing Regulatory Agent - EPA...")
    epa_data = await fetch_epa_violations(test_company)
    print(f"✓ EPA: Violations found: {epa_data.get('violations_found', False)}")
    print(f"  Total 3yr: {epa_data.get('total_violations_3yr', 0)}")

    # Test Reputation Agent
    print("\n[4/6] Testing Reputation Agent (Google News)...")
    news_data = await fetch_news_reputation(test_company)
    print(f"✓ News: Found {news_data.get('articles_found', 0)} recent articles")
    print(f"  Sentiment: {news_data.get('sentiment_score', 0)}/100")
    print(f"  Negative mentions: {news_data.get('negative_mentions', 0)}")

    # Test Cyber Agent - HIBP
    print("\n[5/6] Testing Cyber Agent - HIBP...")
    hibp_data = await check_hibp_breaches(test_company)
    print(f"✓ HIBP: Breaches found: {hibp_data.get('breaches_found', False)}")
    print(f"  Total: {hibp_data.get('total_breaches', 0)}")

    # Test Cyber Agent - CVE
    print("\n[6/6] Testing Cyber Agent - CVE Database...")
    cve_data = await check_cve_database(test_company)
    print(f"✓ CVE: Vulnerabilities found: {cve_data.get('vulnerabilities_found', False)}")
    print(f"  Total: {cve_data.get('total_cves', 0)}")

    print("\n" + "=" * 80)
    print("ALL AGENTS TESTED SUCCESSFULLY")
    print("=" * 80)


async def test_full_investigation():
    """Test full investigation workflow."""
    print("\n\n")
    print("=" * 80)
    print("TESTING FULL INVESTIGATION WORKFLOW")
    print("=" * 80)

    test_company = "Tesla Inc"
    test_assessment_id = "test-assessment-001"

    print(f"\nCompany: {test_company}")
    print(f"Assessment ID: {test_assessment_id}")
    print("\nStarting investigation (this will take ~3 minutes)...\n")

    # Run full investigation
    result = await run_autonomous_investigation(
        company_name=test_company,
        assessment_id=test_assessment_id,
        companies_house_number=None
    )

    print("\n" + "=" * 80)
    print("INVESTIGATION COMPLETE")
    print("=" * 80)

    print(f"\nStatus: {result['status']}")
    print(f"Started: {result['started_at']}")
    print(f"Completed: {result['completed_at']}")
    print(f"Errors: {len(result['errors'])}")

    if result['errors']:
        print("\nErrors encountered:")
        for error in result['errors']:
            print(f"  - {error}")

    # Display final report summary
    final_report = result.get('final_report', {})

    if final_report and final_report.get('report_text'):
        print("\n" + "-" * 80)
        print("REPORT SUMMARY")
        print("-" * 80)
        print(f"Overall Risk Score: {final_report.get('overall_risk_score', 'N/A')}/100")
        print(f"Recommendation: {final_report.get('recommendation', 'N/A')}")

        # Display executive summary
        exec_summary = final_report.get('executive_summary', '')
        if exec_summary:
            print("\nExecutive Summary:")
            print(exec_summary[:500] + "..." if len(exec_summary) > 500 else exec_summary)

        # Display full report (first 2000 chars)
        report_text = final_report.get('report_text', '')
        if report_text:
            print("\n" + "-" * 80)
            print("FULL REPORT (excerpt)")
            print("-" * 80)
            print(report_text[:2000] + "..." if len(report_text) > 2000 else report_text)

    else:
        print("\n⚠ No report generated (check errors)")

    print("\n" + "=" * 80)


async def main():
    """Main test function."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║           AUTONOMOUS INVESTIGATION AGENT - TEST SUITE                     ║
║                                                                           ║
║  This script tests the multi-agent investigation system that autonomously ║
║  investigates companies using free public data sources.                   ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
""")

    try:
        # Test 1: Individual agents
        await test_individual_agents()

        # Prompt user to continue
        print("\n\nPress Enter to test full investigation workflow (takes ~3 minutes)...")
        print("Or Ctrl+C to exit now.")
        try:
            input()
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user. Exiting.")
            return

        # Test 2: Full workflow
        await test_full_investigation()

        print("\n\n✓ ALL TESTS COMPLETED SUCCESSFULLY")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
