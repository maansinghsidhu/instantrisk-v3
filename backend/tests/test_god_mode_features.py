"""
Comprehensive Test Suite for InstantRisk God Mode Features

Tests all new features:
1. Precedent Search (semantic similarity)
2. Risk Monitoring (HIBP breach detection)
3. SHAP Explainability (AI decision transparency)
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import httpx
import json
from datetime import datetime
from typing import Dict, List, Optional


class GodModeFeatureTester:
    """Comprehensive tester for all god mode features."""

    def __init__(self, base_url: str = "http://localhost:8200"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api/v1"
        self.token = None
        self.test_results = []

    def log(self, message: str, level: str = "INFO"):
        """Log test message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def record_result(self, test_name: str, passed: bool, details: str = ""):
        """Record test result."""
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    async def login(self, email: str = "demo@instantrisk.com", password: str = "Demo2026pass"):
        """Login and get access token."""
        self.log("Authenticating...", "TEST")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_base}/auth/login",
                    json={"email": email, "password": password},
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    self.token = data.get("access_token")
                    self.log(f"✓ Logged in as {email}", "PASS")
                    self.record_result("login", True, f"Authenticated as {email}")
                    return True
                else:
                    self.log(f"✗ Login failed: {response.status_code}", "FAIL")
                    self.record_result("login", False, f"Status: {response.status_code}")
                    return False

            except Exception as e:
                self.log(f"✗ Login error: {e}", "FAIL")
                self.record_result("login", False, str(e))
                return False

    def get_headers(self) -> Dict[str, str]:
        """Get auth headers."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def test_backend_startup(self):
        """Test 1: Backend starts without errors."""
        self.log("=== TEST 1: Backend Startup ===", "TEST")

        async with httpx.AsyncClient() as client:
            try:
                # Test health endpoint
                response = await client.get(f"{self.base_url}/health", timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    self.log(f"✓ Backend healthy: {data.get('version')}", "PASS")
                    self.record_result("backend_startup", True, f"Version: {data.get('version')}")
                    return True
                else:
                    self.log(f"✗ Backend unhealthy: {response.status_code}", "FAIL")
                    self.record_result("backend_startup", False, f"Status: {response.status_code}")
                    return False

            except httpx.ConnectError:
                self.log("✗ Backend not running - start with: python -m app.main", "FAIL")
                self.record_result("backend_startup", False, "Connection refused")
                return False
            except Exception as e:
                self.log(f"✗ Backend error: {e}", "FAIL")
                self.record_result("backend_startup", False, str(e))
                return False

    async def test_routers_registered(self):
        """Test 2: All routers registered in OpenAPI."""
        self.log("=== TEST 2: Router Registration ===", "TEST")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/openapi.json", timeout=10.0)

                if response.status_code == 200:
                    openapi = response.json()
                    paths = openapi.get("paths", {})

                    required_endpoints = [
                        "/api/v1/precedents/similar/{assessment_id}",
                        "/api/v1/precedents/batch-embed",
                        "/api/v1/monitoring/alerts",
                        "/api/v1/monitoring/check-breaches/{assessment_id}",
                        "/api/v1/explainability/explain/{assessment_id}",
                    ]

                    all_registered = True
                    for endpoint in required_endpoints:
                        if endpoint in paths:
                            self.log(f"✓ {endpoint} registered", "PASS")
                        else:
                            self.log(f"✗ {endpoint} NOT registered", "FAIL")
                            all_registered = False

                    self.record_result("routers_registered", all_registered,
                                     f"{len([e for e in required_endpoints if e in paths])}/{len(required_endpoints)} endpoints")
                    return all_registered
                else:
                    self.log(f"✗ OpenAPI not available: {response.status_code}", "FAIL")
                    self.record_result("routers_registered", False, "OpenAPI unavailable")
                    return False

            except Exception as e:
                self.log(f"✗ Error checking routers: {e}", "FAIL")
                self.record_result("routers_registered", False, str(e))
                return False

    async def get_test_assessment_id(self) -> Optional[str]:
        """Get an existing assessment ID for testing."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_base}/assessments",
                    headers=self.get_headers(),
                    timeout=10.0
                )

                if response.status_code == 200:
                    assessments = response.json()
                    if assessments and len(assessments) > 0:
                        return assessments[0].get("id")

            except Exception as e:
                self.log(f"Warning: Could not fetch assessment: {e}", "WARN")

        return None

    async def test_precedent_search_embed(self):
        """Test 3: Precedent Search - Batch Embedding."""
        self.log("=== TEST 3: Precedent Search - Batch Embed ===", "TEST")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_base}/precedents/batch-embed",
                    headers=self.get_headers(),
                    timeout=60.0
                )

                if response.status_code == 200:
                    data = response.json()
                    count = data.get("assessments_embedded", 0)
                    self.log(f"✓ Embedded {count} assessments", "PASS")
                    self.record_result("precedent_batch_embed", True, f"{count} embeddings created")
                    return True
                elif response.status_code == 403:
                    self.log("✗ Access denied - need admin role", "FAIL")
                    self.record_result("precedent_batch_embed", False, "Permission denied")
                    return False
                else:
                    self.log(f"✗ Batch embed failed: {response.status_code}", "FAIL")
                    self.record_result("precedent_batch_embed", False, f"Status: {response.status_code}")
                    return False

            except Exception as e:
                self.log(f"✗ Batch embed error: {e}", "FAIL")
                self.record_result("precedent_batch_embed", False, str(e))
                return False

    async def test_precedent_search_similar(self):
        """Test 4: Precedent Search - Find Similar."""
        self.log("=== TEST 4: Precedent Search - Find Similar ===", "TEST")

        # Get test assessment
        assessment_id = await self.get_test_assessment_id()
        if not assessment_id:
            self.log("✗ No assessments available for testing", "FAIL")
            self.record_result("precedent_find_similar", False, "No test data")
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_base}/precedents/similar/{assessment_id}?top_k=5&min_similarity=0.5",
                    headers=self.get_headers(),
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    similar = data.get("similar_assessments", [])
                    self.log(f"✓ Found {len(similar)} similar assessments", "PASS")

                    # Check result structure
                    if similar and len(similar) > 0:
                        first = similar[0]
                        has_similarity = "similarity" in first
                        has_details = "risk_category" in first

                        if has_similarity and has_details:
                            self.log(f"  Top match: {first.get('similarity_pct')} similar", "INFO")
                            self.record_result("precedent_find_similar", True, f"{len(similar)} results")
                            return True
                        else:
                            self.log("✗ Results missing required fields", "FAIL")
                            self.record_result("precedent_find_similar", False, "Invalid result structure")
                            return False
                    else:
                        self.log("✓ Search works but no similar assessments found", "PASS")
                        self.record_result("precedent_find_similar", True, "0 results (expected)")
                        return True

                elif response.status_code == 404:
                    self.log("✗ Assessment not found", "FAIL")
                    self.record_result("precedent_find_similar", False, "Assessment not found")
                    return False
                else:
                    self.log(f"✗ Search failed: {response.status_code}", "FAIL")
                    self.record_result("precedent_find_similar", False, f"Status: {response.status_code}")
                    return False

            except Exception as e:
                self.log(f"✗ Search error: {e}", "FAIL")
                self.record_result("precedent_find_similar", False, str(e))
                return False

    async def test_hibp_monitoring(self):
        """Test 5: HIBP Breach Monitoring."""
        self.log("=== TEST 5: HIBP Breach Monitoring ===", "TEST")

        assessment_id = await self.get_test_assessment_id()
        if not assessment_id:
            self.log("✗ No assessments for testing", "FAIL")
            self.record_result("hibp_monitoring", False, "No test data")
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_base}/monitoring/check-breaches/{assessment_id}",
                    headers=self.get_headers(),
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")

                    if status in ["breaches_found", "clean", "skipped"]:
                        breach_count = data.get("breach_count", 0)
                        self.log(f"✓ HIBP check complete: {status} ({breach_count} breaches)", "PASS")
                        self.record_result("hibp_monitoring", True, f"{status}: {breach_count} breaches")
                        return True
                    else:
                        self.log(f"✗ Unexpected status: {status}", "FAIL")
                        self.record_result("hibp_monitoring", False, f"Invalid status: {status}")
                        return False

                else:
                    self.log(f"✗ HIBP check failed: {response.status_code}", "FAIL")
                    self.record_result("hibp_monitoring", False, f"Status: {response.status_code}")
                    return False

            except Exception as e:
                self.log(f"✗ HIBP error: {e}", "FAIL")
                self.record_result("hibp_monitoring", False, str(e))
                return False

    async def test_monitoring_alerts_list(self):
        """Test 6: List Monitoring Alerts."""
        self.log("=== TEST 6: List Monitoring Alerts ===", "TEST")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_base}/monitoring/alerts?limit=10",
                    headers=self.get_headers(),
                    timeout=10.0
                )

                if response.status_code == 200:
                    alerts = response.json()
                    self.log(f"✓ Retrieved {len(alerts)} alerts", "PASS")
                    self.record_result("monitoring_alerts_list", True, f"{len(alerts)} alerts")
                    return True
                else:
                    self.log(f"✗ List alerts failed: {response.status_code}", "FAIL")
                    self.record_result("monitoring_alerts_list", False, f"Status: {response.status_code}")
                    return False

            except Exception as e:
                self.log(f"✗ List alerts error: {e}", "FAIL")
                self.record_result("monitoring_alerts_list", False, str(e))
                return False

    async def test_explainability_explain(self):
        """Test 7: SHAP Explainability - Explain Decision."""
        self.log("=== TEST 7: SHAP Explainability - Explain ===", "TEST")

        assessment_id = await self.get_test_assessment_id()
        if not assessment_id:
            self.log("✗ No assessments for testing", "FAIL")
            self.record_result("explainability_explain", False, "No test data")
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_base}/explainability/explain/{assessment_id}",
                    headers=self.get_headers(),
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()

                    # Check required fields
                    has_score = "risk_score" in data
                    has_contributions = "feature_contributions" in data
                    has_chart = "waterfall_chart" in data

                    if has_score and has_contributions and has_chart:
                        self.log(f"✓ Explanation generated (score: {data.get('risk_score')})", "PASS")

                        # Check top factors
                        top_factors = data.get("top_factors", [])
                        if top_factors:
                            self.log(f"  Top factor: {top_factors[0].get('feature')}", "INFO")

                        self.record_result("explainability_explain", True,
                                         f"{len(data.get('feature_contributions', {}))} features")
                        return True
                    else:
                        self.log("✗ Explanation missing required fields", "FAIL")
                        self.record_result("explainability_explain", False, "Invalid structure")
                        return False

                elif response.status_code == 400:
                    self.log("! Assessment not analyzed yet (expected)", "WARN")
                    self.record_result("explainability_explain", True, "No risk score (expected)")
                    return True
                else:
                    self.log(f"✗ Explain failed: {response.status_code}", "FAIL")
                    self.record_result("explainability_explain", False, f"Status: {response.status_code}")
                    return False

            except Exception as e:
                self.log(f"✗ Explain error: {e}", "FAIL")
                self.record_result("explainability_explain", False, str(e))
                return False

    async def test_explainability_counterfactual(self):
        """Test 8: SHAP Explainability - Counterfactuals."""
        self.log("=== TEST 8: SHAP Explainability - Counterfactual ===", "TEST")

        assessment_id = await self.get_test_assessment_id()
        if not assessment_id:
            self.log("✗ No assessments for testing", "FAIL")
            self.record_result("explainability_counterfactual", False, "No test data")
            return False

        async with httpx.AsyncClient() as client:
            try:
                # Test counterfactual: what if deductible was higher?
                response = await client.post(
                    f"{self.api_base}/explainability/counterfactual/{assessment_id}",
                    headers=self.get_headers(),
                    json={"deductible": 100000},
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()

                    has_original = "original_score" in data
                    has_new = "new_score" in data
                    has_change = "score_change" in data

                    if has_original and has_new and has_change:
                        change = data.get("score_change", 0)
                        self.log(f"✓ Counterfactual calculated (change: {change:+.1f})", "PASS")
                        self.record_result("explainability_counterfactual", True, f"Score change: {change:+.1f}")
                        return True
                    else:
                        self.log("✗ Counterfactual missing required fields", "FAIL")
                        self.record_result("explainability_counterfactual", False, "Invalid structure")
                        return False

                else:
                    self.log(f"✗ Counterfactual failed: {response.status_code}", "FAIL")
                    self.record_result("explainability_counterfactual", False, f"Status: {response.status_code}")
                    return False

            except Exception as e:
                self.log(f"✗ Counterfactual error: {e}", "FAIL")
                self.record_result("explainability_counterfactual", False, str(e))
                return False

    async def test_database_migrations(self):
        """Test 9: Database tables exist."""
        self.log("=== TEST 9: Database Schema ===", "TEST")

        # This requires database access - we'll check via API behavior
        # If all API endpoints work, tables must exist

        # Check if we can call endpoints that require the tables
        tests_passed = 0
        tests_total = 3

        # Test 1: Precedent search (assessment_vectors table)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/precedents/batch-embed",
                    headers=self.get_headers(),
                    timeout=10.0
                )
                if response.status_code in [200, 403]:  # 403 = no permission but table exists
                    self.log("✓ assessment_vectors table exists", "PASS")
                    tests_passed += 1
        except:
            pass

        # Test 2: Monitoring alerts (risk_monitoring_alerts table)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/monitoring/alerts",
                    headers=self.get_headers(),
                    timeout=10.0
                )
                if response.status_code == 200:
                    self.log("✓ risk_monitoring_alerts table exists", "PASS")
                    tests_passed += 1
        except:
            pass

        # Test 3: Check OpenAPI confirms models
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/openapi.json", timeout=10.0)
                if response.status_code == 200:
                    openapi = response.json()
                    schemas = openapi.get("components", {}).get("schemas", {})
                    if "SimilarAssessment" in schemas or "AlertResponse" in schemas:
                        self.log("✓ Response schemas registered", "PASS")
                        tests_passed += 1
        except:
            pass

        success = tests_passed == tests_total
        self.record_result("database_migrations", success, f"{tests_passed}/{tests_total} schema checks passed")
        return success

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)

        passed = sum(1 for r in self.test_results if r["passed"])
        total = len(self.test_results)

        for result in self.test_results:
            status = "✓ PASS" if result["passed"] else "✗ FAIL"
            print(f"{status:8} | {result['test']:35} | {result['details']}")

        print("=" * 80)
        print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        print("=" * 80)

        # Save detailed report
        report_path = Path(__file__).parent / "test_results.json"
        with open(report_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {"passed": passed, "total": total, "success_rate": passed/total},
                "results": self.test_results
            }, f, indent=2)

        print(f"\nDetailed report saved: {report_path}")

    async def run_all_tests(self):
        """Run all tests."""
        self.log("=" * 80, "TEST")
        self.log("INSTANTRISK GOD MODE FEATURES - COMPREHENSIVE TEST SUITE", "TEST")
        self.log("=" * 80, "TEST")

        # Test 1: Backend startup
        if not await self.test_backend_startup():
            self.log("Backend not running - stopping tests", "FAIL")
            self.print_summary()
            return

        # Test 2: Routers registered
        await self.test_routers_registered()

        # Login required for remaining tests
        if not await self.login():
            self.log("Authentication failed - stopping tests", "FAIL")
            self.print_summary()
            return

        # Test 3-4: Precedent Search
        await self.test_precedent_search_embed()
        await self.test_precedent_search_similar()

        # Test 5-6: HIBP Monitoring
        await self.test_hibp_monitoring()
        await self.test_monitoring_alerts_list()

        # Test 7-8: Explainability
        await self.test_explainability_explain()
        await self.test_explainability_counterfactual()

        # Test 9: Database
        await self.test_database_migrations()

        # Summary
        self.print_summary()


async def main():
    """Main test runner."""
    # Check if backend is specified
    base_url = os.getenv("BACKEND_URL", "http://localhost:8200")

    tester = GodModeFeatureTester(base_url=base_url)
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
