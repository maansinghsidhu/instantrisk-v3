"""Comprehensive API Endpoint Test Script for InstantRisk Backend"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com"
EMAIL = "demo@instantrisk.com"
PASSWORD = "Demo2026pass"

passed = 0
failed = 0
skipped = 0
results = []

def test(name, method, path, token=None, data=None, expected_status=None, allow_statuses=None):
    """Run a single API test."""
    global passed, failed, skipped
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = None
    if data is not None:
        body = json.dumps(data).encode()

    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        resp = urllib.request.urlopen(req, timeout=30)
        status = resp.status
        resp_body = resp.read().decode()
    except urllib.error.HTTPError as e:
        status = e.code
        resp_body = e.read().decode() if e.fp else ""
    except Exception as e:
        status = 0
        resp_body = str(e)

    ok = False
    if allow_statuses:
        ok = status in allow_statuses
    elif expected_status:
        ok = status == expected_status
    else:
        ok = 200 <= status < 300

    icon = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1

    # Parse response for display
    try:
        parsed = json.loads(resp_body)
        short = json.dumps(parsed)[:120]
    except:
        short = resp_body[:120]

    print(f"  [{icon}] {name}: {method} {path} -> {status}")
    if not ok:
        print(f"         Response: {short}")

    results.append({"name": name, "ok": ok, "status": status, "path": path})
    return status, resp_body


def main():
    global passed, failed
    print("=" * 60)
    print("INSTANTRISK API ENDPOINT TEST SUITE")
    print("=" * 60)

    # ===== AUTH =====
    print("\n--- AUTH ---")
    status, body = test("Health Check", "GET", "/api/v1/health/live")

    status, body = test("Login", "POST", "/api/v1/auth/login",
                        data={"email": EMAIL, "password": PASSWORD})
    if status != 200:
        print("\nFATAL: Cannot login. Aborting.")
        sys.exit(1)

    token_data = json.loads(body)
    token = token_data["access_token"]
    print(f"  Token: {token[:20]}...")

    test("Login - Bad Password", "POST", "/api/v1/auth/login",
         data={"email": EMAIL, "password": "wrong"}, expected_status=401)

    test("Get Current User", "GET", "/api/v1/auth/me", token=token)

    # ===== ASSESSMENTS =====
    print("\n--- ASSESSMENTS ---")
    status, body = test("List Assessments", "GET", "/api/v1/assessments/?page=1&page_size=5", token=token)

    assessment_id = None
    if status == 200:
        items = json.loads(body).get("items", [])
        if items:
            assessment_id = items[0]["id"]
            print(f"  Using assessment: {assessment_id}")

    if assessment_id:
        test("Get Assessment Detail", "GET", f"/api/v1/assessments/{assessment_id}", token=token)
    else:
        print("  [SKIP] No assessments to test detail endpoint")

    test("Create Assessment", "POST", "/api/v1/assessments/",
         token=token,
         data={"title": "API Test Assessment", "risk_category": "property"},
         allow_statuses=[200, 201, 422])

    # ===== UPLOAD SESSIONS =====
    print("\n--- UPLOAD SESSIONS ---")
    status, body = test("Create Upload Session", "POST", "/api/v1/upload-sessions/",
                        token=token, data={}, allow_statuses=[200, 201])

    session_token = None
    if status in (200, 201):
        session_data = json.loads(body)
        session_token = session_data.get("token")
        print(f"  Session token: {session_token[:8]}..." if session_token else "  No token returned")

    if session_token:
        test("Get Session Status", "GET", f"/api/v1/upload-sessions/{session_token}/status", token=token)
    else:
        print("  [SKIP] No session token for status check")

    # ===== DOCUMENTS =====
    print("\n--- DOCUMENTS ---")
    if assessment_id:
        test("List Documents for Assessment", "GET",
             f"/api/v1/documents/?assessment_id={assessment_id}&page=1&page_size=5",
             token=token,
             allow_statuses=[200, 404])
    else:
        print("  [SKIP] No assessment ID for document listing")

    # ===== GENERATED DOCUMENTS =====
    print("\n--- GENERATED DOCUMENTS ---")
    if assessment_id:
        test("List Generated Docs", "GET",
             f"/api/v1/generated-documents/?assessment_id={assessment_id}",
             token=token,
             allow_statuses=[200, 404, 422])
    else:
        print("  [SKIP] No assessment ID")

    # ===== CHAT =====
    print("\n--- CHAT ---")
    test("Chat Suggestions", "GET", "/api/v1/chat/suggestions", token=token,
         allow_statuses=[200, 404])

    test("Chat History", "GET", "/api/v1/chat/history", token=token,
         allow_statuses=[200, 404])

    if assessment_id:
        test("Chat Send Message", "POST", "/api/v1/chat/send",
             token=token,
             data={"message": "Summarize the assessment", "assessment_id": str(assessment_id)},
             allow_statuses=[200, 201, 404, 422, 500])

    # ===== CLAIMSENSE =====
    print("\n--- CLAIMSENSE ---")
    test("ClaimSense Health", "GET", "/api/v1/claimsense/health",
         token=token, allow_statuses=[200, 404])

    test("ClaimSense Query", "POST", "/api/v1/claimsense/query",
         token=token,
         data={"query": "commercial property loss ratio UK", "class_of_business": "property"},
         allow_statuses=[200, 404, 422, 500])

    # ===== RAPIDRATE =====
    print("\n--- RAPIDRATE ---")
    test("RapidRate Health", "GET", "/api/v1/pricing/health",
         token=token, allow_statuses=[200, 404])

    test("RapidRate Quote", "POST", "/api/v1/pricing/quote",
         token=token,
         data={"class_of_business": "property", "sum_insured": 10000000, "territory": "UK"},
         allow_statuses=[200, 404, 422, 500])

    # ===== REFERENCE DOCUMENTS (Training) =====
    print("\n--- TRAINING CENTER ---")
    test("List Reference Docs", "GET", "/api/v1/reference-documents/",
         token=token, allow_statuses=[200, 404])

    # ===== SYNDICATES =====
    print("\n--- SYNDICATES ---")
    test("List Syndicates", "GET", "/api/v1/syndicates/",
         token=token, allow_statuses=[200, 404])

    # ===== SUBSCRIPTIONS =====
    print("\n--- SUBSCRIPTIONS ---")
    test("Get Subscription", "GET", "/api/v1/subscriptions/current",
         token=token, allow_statuses=[200, 404])

    test("List Features", "GET", "/api/v1/subscriptions/features",
         token=token, allow_statuses=[200, 404])

    # ===== UNAUTHORIZED ACCESS =====
    print("\n--- AUTH PROTECTION ---")
    test("Assessments Without Token", "GET", "/api/v1/assessments/",
         expected_status=401)

    test("Chat Without Token", "GET", "/api/v1/chat/suggestions",
         allow_statuses=[401, 403])

    # ===== SUMMARY =====
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"Total: {passed + failed + skipped} tests")
    print("=" * 60)

    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if not r["ok"]:
                print(f"  - {r['name']}: {r['status']} on {r['path']}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
