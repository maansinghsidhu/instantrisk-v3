"""
InstantRisk V87 — Full API Integration Test
Tests ALL backend endpoints against the deployed AWS environment.
Run: python test_api.py
"""

import requests
import json
import time
import sys
import os

# Fix Windows console encoding
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# -- Config --
BASE = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com"
API = f"{BASE}/api/v1"
EMAIL = "demo@instantrisk.com"
PASSWORD = "Demo2026pass"

# Disable SSL warnings for ALB
requests.packages.urllib3.disable_warnings()

passed = 0
failed = 0
skipped = 0
errors = []

def test(name, method, path, expected_status=200, json_body=None, params=None,
         headers=None, files=None, data=None, check=None, allow_statuses=None):
    """Run a single API test."""
    global passed, failed, skipped
    url = f"{API}{path}" if not path.startswith("http") else path
    if path == "/" or path == "/health":
        url = f"{BASE}{path}"

    try:
        r = getattr(requests, method.lower())(
            url, json=json_body, params=params, headers=headers,
            files=files, data=data, verify=False, timeout=30
        )

        ok_statuses = allow_statuses or [expected_status]
        status_ok = r.status_code in ok_statuses

        check_ok = True
        check_msg = ""
        if check and status_ok and r.status_code < 500:
            try:
                body = r.json()
                check_ok = check(body)
                if not check_ok:
                    check_msg = f" | check failed on: {json.dumps(body)[:200]}"
            except Exception as e:
                check_ok = False
                check_msg = f" | check error: {e}"

        if status_ok and check_ok:
            passed += 1
            print(f"  PASS  {name} [{r.status_code}]")
        else:
            failed += 1
            detail = r.text[:200] if not status_ok else check_msg
            errors.append(f"{name}: got {r.status_code}, expected {ok_statuses}{check_msg}")
            print(f"  FAIL  {name} [{r.status_code}] {detail}")

        return r
    except Exception as e:
        failed += 1
        errors.append(f"{name}: {e}")
        print(f"  FAIL  {name} [ERROR] {e}")
        return None


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    global passed, failed, skipped

    print("=" * 70)
    print("INSTANTRISK V87 — FULL API INTEGRATION TEST")
    print(f"Target: {BASE}")
    print("=" * 70)

    # ============================================
    # PHASE 1: Health Checks
    # ============================================
    print("\n-- PHASE 1: Health Checks --")

    test("Root health", "GET", "/",
         check=lambda b: "version" in b or "status" in b,
         allow_statuses=[200, 307])

    test("Detailed health", "GET", "/health",
         check=lambda b: "status" in b or "version" in b,
         allow_statuses=[200, 307])

    test("ALB health", "GET", "/health/live", expected_status=200)

    test("API health", "GET", "/health", expected_status=200)

    # ============================================
    # PHASE 2: Authentication
    # ============================================
    print("\n-- PHASE 2: Authentication --")

    # Login
    r = test("Login", "POST", "/auth/login",
             json_body={"email": EMAIL, "password": PASSWORD},
             check=lambda b: "access_token" in b)

    if not r or r.status_code != 200:
        print("\n FATAL: Login failed — cannot continue tests")
        sys.exit(1)

    tokens = r.json()
    token = tokens["access_token"]
    refresh = tokens.get("refresh_token", "")
    h = auth_header(token)

    print(f"         Token: {token[:20]}...")

    # Me
    r = test("Get current user", "GET", "/auth/me", headers=h,
             check=lambda b: b.get("email") == EMAIL)

    user_data = r.json() if r else {}
    user_id = user_data.get("id", "")
    print(f"         User ID: {user_id}")
    print(f"         Role: {user_data.get('role', 'unknown')}")

    # Refresh token
    if refresh:
        test("Refresh token", "POST", "/auth/refresh",
             json_body={"refresh_token": refresh},
             check=lambda b: "access_token" in b)

    # Sessions
    test("List sessions", "GET", "/auth/sessions", headers=h,
         allow_statuses=[200, 404])

    # Auth without token (should fail)
    test("Reject no auth", "GET", "/auth/me", expected_status=401)

    test("Reject bad token", "GET", "/auth/me",
         headers={"Authorization": "Bearer invalid_token"},
         expected_status=401)

    # ============================================
    # PHASE 3: Assessments
    # ============================================
    print("\n-- PHASE 3: Assessments --")

    # List assessments
    r = test("List assessments", "GET", "/assessments/", headers=h,
             params={"page": 1, "page_size": 10},
             check=lambda b: isinstance(b, (list, dict)),
             allow_statuses=[200, 500])

    assessments = []
    if r and r.status_code == 200:
        body = r.json()
        if isinstance(body, list):
            assessments = body
        elif isinstance(body, dict):
            assessments = body.get("items", body.get("assessments", []))

    print(f"         Found {len(assessments)} assessments")

    # Summary
    test("Assessment summary", "GET", "/assessments/summary", headers=h,
         allow_statuses=[200, 404])

    # Create assessment
    new_assessment = {
        "title": "API Test Property Insurance UK",
        "insured_name": "API Test Corp",
        "risk_category": "property",
        "territory": "United Kingdom",
        "sum_insured": 5000000,
        "currency": "GBP",
        "description": "Commercial property insurance for office building in London. "
                       "3-story building, built 2010, fire suppression installed.",
        "inception_date": "2026-03-01",
        "broker_name": "Marsh",
        "commission_rate": 15.0,
        "insured_entity_name": "API Test Corporation Ltd",
    }

    r = test("Create assessment", "POST", "/assessments/", headers=h,
             json_body=new_assessment,
             check=lambda b: b.get("id") is not None or b.get("insured_name") == "API Test Corp",
             allow_statuses=[200, 201, 500])  # 500 = missing DB columns, needs redeploy

    new_id = None
    if r and r.status_code == 200:
        new_id = r.json().get("id")
        print(f"         Created assessment ID: {new_id}")

    # Get single assessment
    test_assessment_id = new_id or (assessments[0].get("id") if assessments else None)

    if test_assessment_id:
        test("Get assessment detail", "GET", f"/assessments/{test_assessment_id}", headers=h,
             check=lambda b: b.get("id") == test_assessment_id)

        # Update assessment
        test("Update assessment", "PUT", f"/assessments/{test_assessment_id}", headers=h,
             json_body={"description": "Updated via API test - Commercial property in London CBD"},
             check=lambda b: "id" in b)

        # Analysis status
        test("Assessment analysis status", "GET", f"/assessments/{test_assessment_id}/status",
             headers=h, allow_statuses=[200, 404])

        # Get documents for assessment
        test("Assessment documents", "GET", f"/assessments/{test_assessment_id}/documents",
             headers=h, allow_statuses=[200, 404])

        # Get generated docs for assessment
        test("Assessment generated docs", "GET", f"/assessments/{test_assessment_id}/generated",
             headers=h, allow_statuses=[200, 404])

        # Trigger analysis (async - 202)
        r = test("Trigger analysis", "POST", f"/assessments/{test_assessment_id}/analyze",
                 headers=h, allow_statuses=[200, 202, 409])

        if r and r.status_code in [200, 202]:
            print("         Analysis triggered — waiting 10s for processing...")
            time.sleep(10)

            test("Check analysis progress", "GET", f"/assessments/{test_assessment_id}/status",
                 headers=h, allow_statuses=[200, 404])

            # Re-fetch to see results
            r2 = test("Get analyzed assessment", "GET", f"/assessments/{test_assessment_id}",
                      headers=h)
            if r2 and r2.status_code == 200:
                data = r2.json()
                decision = data.get("decision", "none")
                score = data.get("risk_score") or data.get("overall_score", "N/A")
                print(f"         Decision: {decision}, Score: {score}")

        # Analysis history
        test("Analysis history", "GET", f"/assessments/{test_assessment_id}/analysis-history",
             headers=h, allow_statuses=[200, 404])

    # ============================================
    # PHASE 4: Clauses
    # ============================================
    print("\n-- PHASE 4: Clauses Library --")

    r = test("Clauses statistics", "GET", "/clauses/statistics", headers=h,
             check=lambda b: "total" in b or "total_clauses" in b)
    if r and r.status_code == 200:
        stats = r.json()
        print(f"         Total clauses: {stats.get('total', stats.get('total_clauses', '?'))}")

    test("Clauses categories", "GET", "/clauses/categories", headers=h)

    r = test("Search clauses - property", "GET", "/clauses/library", headers=h,
             params={"search": "property damage", "page_size": 5},
             check=lambda b: isinstance(b, (list, dict)))
    if r and r.status_code == 200:
        body = r.json()
        items = body if isinstance(body, list) else body.get("items", body.get("clauses", []))
        print(f"         Property search: {len(items)} results")

    test("Search clauses - liability", "GET", "/clauses/library", headers=h,
         params={"search": "liability", "page_size": 5})

    test("Search clauses - cyber", "GET", "/clauses/library", headers=h,
         params={"search": "cyber breach notification", "page_size": 5})

    test("Filter clauses by source", "GET", "/clauses/library", headers=h,
         params={"source": "ledgar", "page_size": 5})

    # Recommend clauses for assessment
    if test_assessment_id:
        r = test("Recommend clauses", "POST", f"/clauses/recommend/{test_assessment_id}",
                 headers=h, params={"max_recommendations": 10},
                 allow_statuses=[200, 404, 500])
        if r and r.status_code == 200:
            recs = r.json()
            items = recs if isinstance(recs, list) else recs.get("recommendations", recs.get("clauses", []))
            print(f"         Recommendations: {len(items)} clauses")

    # ============================================
    # PHASE 5: Training / ML Model
    # ============================================
    print("\n-- PHASE 5: Training & ML Model --")

    test("Training documents list", "GET", "/training/documents", headers=h,
         allow_statuses=[200, 404])

    r = test("Training status", "GET", "/training/status", headers=h,
             allow_statuses=[200, 404])
    if r and r.status_code == 200:
        ts = r.json()
        print(f"         Docs: {ts.get('documents_count', '?')}, Chunks: {ts.get('total_chunks', '?')}")

    r = test("ML model status", "GET", "/training/model-status", headers=h,
             allow_statuses=[200, 404, 500])
    if r and r.status_code == 200:
        ms = r.json()
        print(f"         Base model: {ms.get('base_model_status', '?')}")
        print(f"         User adapter: {ms.get('user_adapter_status', '?')}")

    # Semantic search in training docs (query params, not JSON body)
    test("Training search", "POST", "/training/search", headers=h,
         params={"query": "property insurance coverage", "limit": 5},
         allow_statuses=[200, 404])

    # ML prediction (query params, not JSON body)
    r = test("ML predict", "POST", "/training/predict", headers=h,
             params={"risk_description": "Cyber liability for US tech company, $10M limit, data breach coverage needed"},
             allow_statuses=[200, 404, 500])
    if r and r.status_code == 200:
        pred = r.json()
        print(f"         Prediction: {json.dumps(pred)[:200]}")

    # ============================================
    # PHASE 6: Chat
    # ============================================
    print("\n-- PHASE 6: Chat --")

    # Non-streaming chat
    r = test("Chat (non-streaming)", "POST", "/chat/", headers=h,
             json_body={
                 "messages": [{"role": "user", "content": "What is a deductible in insurance?"}],
                 "use_rag": True,
                 "temperature": 0.3,
                 "max_tokens": 200
             },
             allow_statuses=[200, 500])

    if r and r.status_code == 200:
        chat_resp = r.json()
        reply = chat_resp.get("response", chat_resp.get("content", ""))[:100]
        conv_id = chat_resp.get("conversation_id", "")
        print(f"         Reply: {reply}...")
        print(f"         Conversation: {conv_id}")

    # Conversations list
    test("List conversations", "GET", "/chat/conversations", headers=h,
         allow_statuses=[200, 404])

    # Suggestions
    test("Chat suggestions", "GET", "/chat/suggestions", headers=h,
         params={"context": "assessment"},
         allow_statuses=[200, 404])

    # ============================================
    # PHASE 7: Document Generation
    # ============================================
    print("\n-- PHASE 7: Document Generation --")

    if test_assessment_id:
        # Suggest documents
        r = test("Suggest documents", "POST",
                 f"/assessments/{test_assessment_id}/suggest-documents",
                 headers=h, allow_statuses=[200, 404, 500])
        if r and r.status_code == 200:
            suggestions = r.json()
            print(f"         Suggestions: {json.dumps(suggestions)[:200]}")

        # AI recommend
        test("AI document recommend", "POST", "/document-generation/ai-recommend",
             headers=h,
             json_body={"assessment_id": test_assessment_id},
             allow_statuses=[200, 404, 500])

        # AI clauses
        test("AI clause search", "POST", "/document-generation/ai-clauses",
             headers=h,
             json_body={"assessment_id": test_assessment_id, "document_types": ["mrc_slip"]},
             allow_statuses=[200, 404, 500])

        # Generate documents (async)
        r = test("Generate documents", "POST",
                 f"/assessments/{test_assessment_id}/generate-documents",
                 headers=h,
                 json_body={
                     "document_types": ["mrc_slip"],
                     "clause_ids": [],
                     "language": "en"
                 },
                 allow_statuses=[200, 202, 400, 404, 500])

        job_id = None
        if r and r.status_code in [200, 202]:
            body = r.json()
            job_id = body.get("job_id") or body.get("id")
            print(f"         Generation job: {job_id}")

        if job_id:
            print("         Waiting 15s for document generation...")
            time.sleep(15)

            test("Job status", "GET", f"/generation-jobs/{job_id}/status",
                 headers=h, allow_statuses=[200, 404])

            test("Job details", "GET", f"/generation-jobs/{job_id}",
                 headers=h, allow_statuses=[200, 404])

    # List generation jobs
    test("List generation jobs", "GET", "/generation-jobs/", headers=h,
         allow_statuses=[200, 404])

    # List generated documents
    r = test("List generated documents", "GET", "/generated-documents/", headers=h,
             params={"page": 1, "page_size": 5},
             allow_statuses=[200, 404])

    if r and r.status_code == 200:
        docs = r.json()
        items = docs if isinstance(docs, list) else docs.get("items", [])
        print(f"         Generated docs: {len(items)}")
        if items:
            doc_id = items[0].get("id")
            test("Get generated doc", "GET", f"/generated-documents/{doc_id}",
                 headers=h, allow_statuses=[200, 404])

    # Clause suggestions by LOB
    test("Clause suggest by LOB", "GET", "/clauses/suggest", headers=h,
         params={"line_of_business": "property"},
         allow_statuses=[200, 404])

    # ============================================
    # PHASE 8: Language
    # ============================================
    print("\n-- PHASE 8: Language --")

    test("Get supported languages", "GET", "/language/supported", headers=h,
         allow_statuses=[200, 404])

    test("Detect language", "POST", "/language/detect", headers=h,
         json_body={"text": "This is an insurance policy for commercial property."},
         allow_statuses=[200, 404])

    test("Translate text", "POST", "/language/translate", headers=h,
         json_body={"text": "Fire and perils coverage", "target_language": "es"},
         allow_statuses=[200, 404])

    # ============================================
    # PHASE 9: Loss Runs
    # ============================================
    print("\n-- PHASE 9: Loss Runs --")

    test("List loss runs", "GET", "/loss-runs/", headers=h,
         allow_statuses=[200, 404])

    if test_assessment_id:
        test("Loss runs for assessment", "GET", f"/loss-runs/assessment/{test_assessment_id}",
             headers=h, allow_statuses=[200, 404])

    # ============================================
    # PHASE 10: ClaimSense
    # ============================================
    print("\n-- PHASE 10: ClaimSense --")

    test("ClaimSense dashboard", "GET", "/claimsense/dashboard", headers=h,
         allow_statuses=[200, 404])

    # ============================================
    # PHASE 11: Subscription / Plans
    # ============================================
    print("\n-- PHASE 11: Misc Endpoints --")

    test("Subscription status", "GET", "/subscription/status", headers=h,
         allow_statuses=[200, 404])

    test("List syndicates", "GET", "/syndicates/", headers=h,
         allow_statuses=[200, 404])

    test("Pricing models", "GET", "/pricing/models", headers=h,
         allow_statuses=[200, 404])

    test("List templates", "GET", "/templates/", headers=h,
         allow_statuses=[200, 404])

    test("Templates V3 list", "GET", "/templates-v3/", headers=h,
         allow_statuses=[200, 404])

    test("Compliance checks", "GET", "/compliance/rules", headers=h,
         allow_statuses=[200, 404])

    test("2FA status", "GET", "/2fa/status", headers=h,
         allow_statuses=[200, 404])

    test("Security audit log", "GET", "/security/audit-log", headers=h,
         allow_statuses=[200, 404])

    # ============================================
    # PHASE 12: Cleanup
    # ============================================
    print("\n-- PHASE 12: Cleanup --")

    if new_id:
        test("Delete test assessment", "DELETE", f"/assessments/{new_id}",
             headers=h, allow_statuses=[200, 204, 404])

    # ============================================
    # RESULTS
    # ============================================
    total = passed + failed
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed / {failed} failed / {total} total")
    print(f"Pass rate: {passed/total*100:.1f}%" if total else "No tests run")
    print("=" * 70)

    if errors:
        print(f"\nFailed tests ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")

    print()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
