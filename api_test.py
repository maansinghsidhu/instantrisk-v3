"""InstantRisk API Integration Test Suite — v3 with improved diagnostics"""
import requests
import json
import sys
import time

BASE = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com/api/v1"
EMAIL = "demo@instantrisk.com"
PASSWORD = "Demo2026pass"

results = []
token = None
user_id = None

def test(name, method, endpoint, expected_status=200, json_body=None, auth=True, timeout=30):
    """Run a single API test"""
    global token
    url = f"{BASE}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if auth and token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        elif method == "POST":
            r = requests.post(url, headers=headers, json=json_body, timeout=timeout, allow_redirects=True)
        elif method == "PUT":
            r = requests.put(url, headers=headers, json=json_body, timeout=timeout, allow_redirects=True)
        elif method == "DELETE":
            r = requests.delete(url, headers=headers, timeout=timeout, allow_redirects=True)
        else:
            raise ValueError(f"Unknown method: {method}")

        status_ok = r.status_code == expected_status
        try:
            body = r.json()
        except:
            body = r.text[:300] if r.text else "(empty)"

        icon = "PASS" if status_ok else "FAIL"
        print(f"[{icon}] {name}: {r.status_code} (expected {expected_status})")

        if not status_ok:
            detail = body.get("detail", body) if isinstance(body, dict) else str(body)[:300]
            print(f"       Response: {detail}")

        results.append({"name": name, "pass": status_ok, "status": r.status_code})
        return body if status_ok else None
    except requests.exceptions.Timeout:
        print(f"[FAIL] {name}: TIMEOUT after {timeout}s")
        results.append({"name": name, "pass": False, "status": "timeout"})
        return None
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        results.append({"name": name, "pass": False, "status": str(e)})
        return None


print("=" * 70)
print("INSTANTRISK API INTEGRATION TEST SUITE v3")
print(f"Base URL: {BASE}")
print("=" * 70)

# ═══════════════════════════════════════════════════════════════════════
# PHASE 1: Health Checks
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 1: Health Checks ---")

test("Health live", "GET", "/health/live", auth=False)
test("Health full", "GET", "/health", auth=False)

# ═══════════════════════════════════════════════════════════════════════
# PHASE 2: Authentication
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 2: Authentication ---")

# Login
login_data = test("Login", "POST", "/auth/login", json_body={"email": EMAIL, "password": PASSWORD}, auth=False)
if login_data:
    token = login_data.get("access_token")
    user_id = login_data.get("user", {}).get("id")
    user_name = login_data.get("user", {}).get("full_name")
    print(f"       Token: {token[:30]}... User: {user_name} ({user_id})")

# Bad login
test("Bad login", "POST", "/auth/login", json_body={"email": "bad@test.com", "password": "wrong"}, auth=False, expected_status=401)

# Get current user
me_data = test("Get current user", "GET", "/auth/me")
if me_data:
    print(f"       Email: {me_data.get('email')}, Role: {me_data.get('role')}")

# 2FA status
test("2FA status", "GET", "/2fa/status")

# Sessions
sessions = test("Active sessions", "GET", "/auth/sessions")
if sessions:
    s_list = sessions.get("sessions", sessions) if isinstance(sessions, dict) else sessions
    print(f"       Sessions: {len(s_list) if isinstance(s_list, list) else '?'}")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 3: Subscriptions (note: /subscription singular)
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 3: Subscriptions ---")

sub_data = test("Get subscription", "GET", "/subscription")
if sub_data:
    plan = sub_data.get("tier", sub_data.get("plan", "?"))
    print(f"       Tier: {plan}")

test("Subscription limits", "GET", "/subscription/limits")
test("Subscription features", "GET", "/subscription/features")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 4: Assessments
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 4: Assessments ---")

# Assessment summary first (always works)
summary = test("Assessment summary", "GET", "/assessments/summary")
if summary:
    total = summary.get("total_assessments", summary.get("total", "?"))
    print(f"       Total: {total}")

# List assessments
assessments = test("List assessments", "GET", "/assessments/")
assessment_id = None
if assessments:
    items = assessments.get("items", assessments.get("assessments", []))
    if isinstance(assessments, list):
        items = assessments
    print(f"       Count: {len(items)}")
    if items:
        assessment_id = items[0].get("id")
        print(f"       First: id={assessment_id}, status={items[0].get('status')}")

# Create a new assessment
new_assessment = test("Create assessment", "POST", "/assessments/", expected_status=201, json_body={
    "title": "API Test - Cyber Liability Assessment",
    "description": "Cyber liability risk assessment for a UK tech company.",
    "risk_category": "cyber",
    "territory": "United Kingdom",
    "sum_insured": 5000000,
    "premium": 125000,
    "insured_name": "Test Corp Ltd",
})
new_assessment_id = None
if new_assessment:
    new_assessment_id = new_assessment.get("id")
    print(f"       Created: id={new_assessment_id}")

# Use whichever assessment ID we have
test_assessment_id = new_assessment_id or assessment_id
if not test_assessment_id:
    print("       WARNING: No assessment ID available - some tests will be skipped")

# Get specific assessment
if test_assessment_id:
    detail = test(f"Get assessment detail", "GET", f"/assessments/{test_assessment_id}")
    if detail:
        print(f"       Title: {detail.get('title', '?')[:40]}, Status: {detail.get('status', '?')}")

    test("Assessment status", "GET", f"/assessments/{test_assessment_id}/status")
    test("Assessment documents", "GET", f"/assessments/{test_assessment_id}/documents")
    test("Assessment generated docs", "GET", f"/assessments/{test_assessment_id}/generated")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 5: Clauses
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 5: Clauses Library ---")

stats = test("Clause statistics", "GET", "/clauses/statistics")
if stats:
    print(f"       Total: {stats.get('total_clauses', '?')}, Sources: {list(stats.get('sources', {}).keys())}")

cats = test("Clause categories", "GET", "/clauses/categories")
if cats:
    cat_list = cats if isinstance(cats, list) else cats.get("categories", [])
    print(f"       Categories: {len(cat_list)}")

lib = test("Clause library (page 1)", "GET", "/clauses/library?limit=5")
if lib:
    items = lib if isinstance(lib, list) else lib.get("clauses", lib.get("items", []))
    print(f"       Clauses: {len(items)}")
    if items:
        print(f"       First: {items[0].get('name', items[0].get('title', '?'))[:60]}")

# Recommend clauses for an assessment
if test_assessment_id:
    recs = test("Recommend clauses", "POST", f"/clauses/recommend/{test_assessment_id}")
    if recs:
        clause_list = recs if isinstance(recs, list) else recs.get("clauses", recs.get("recommended", []))
        print(f"       Recommended: {len(clause_list)} clauses")
        for c in (clause_list[:3] if isinstance(clause_list, list) else []):
            name = c.get("name", c.get("title", "?"))
            score = c.get("relevance_score", c.get("score", "?"))
            print(f"         - {name[:50]} (score: {score})")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 6: Templates
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 6: Templates ---")

test("Template categories", "GET", "/templates/categories")
templates = test("List templates", "GET", "/templates/")
if not templates:
    templates = test("List templates (no slash)", "GET", "/templates")
test("Template clauses", "GET", "/templates/clauses")

# Templates V3
test("V3 policies", "GET", "/templates-v3/policies")
test("V3 clauses", "GET", "/templates-v3/clauses")
test("V3 lines of business", "GET", "/templates-v3/lines")
test("V3 sections", "GET", "/templates-v3/sections?line_of_business=cyber")
test("V3 search", "GET", "/templates-v3/search?q=cyber")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 7: Chat
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 7: Chat ---")

convos = test("List conversations", "GET", "/chat/conversations")
if convos:
    c_list = convos if isinstance(convos, list) else convos.get("conversations", [])
    print(f"       Conversations: {len(c_list)}")
    if c_list:
        convo_id = c_list[0].get("id", c_list[0].get("conversation_id"))
        if convo_id:
            history = test("Conversation history", "GET", f"/chat/history/{convo_id}")
            if history:
                msgs = history if isinstance(history, list) else history.get("messages", [])
                print(f"       Messages in first convo: {len(msgs)}")

test("Chat suggestions", "GET", "/chat/suggestions")

# Send a chat message
chat_resp = test("Send chat message", "POST", "/chat/", json_body={
    "messages": [{"role": "user", "content": "What is a retention in insurance?"}],
    "use_rag": True,
    "max_tokens": 200,
}, timeout=60)
if chat_resp:
    reply = chat_resp.get("response", chat_resp.get("message", chat_resp.get("content", "?")))
    print(f"       AI Reply: {str(reply)[:100]}...")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 8: Training
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 8: Training ---")

train_docs = test("Training documents", "GET", "/training/documents")
if train_docs:
    t_list = train_docs if isinstance(train_docs, list) else train_docs.get("documents", [])
    print(f"       Training docs: {len(t_list)}")

train_status = test("Training status", "GET", "/training/status")
if train_status:
    print(f"       Status: {json.dumps(train_status)[:100]}")

model_status = test("Model status", "GET", "/training/model-status")
if model_status:
    print(f"       Model: {json.dumps(model_status)[:100]}")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 9: Documents
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 9: Documents ---")

docs = test("List documents", "GET", "/documents/")
if docs:
    d_list = docs if isinstance(docs, list) else docs.get("documents", docs.get("items", []))
    print(f"       Documents: {len(d_list)}")

ref_docs = test("Reference documents", "GET", "/reference-documents/")
if ref_docs:
    r_list = ref_docs if isinstance(ref_docs, list) else ref_docs.get("documents", [])
    print(f"       Reference docs: {len(r_list)}")

test("Reference doc categories", "GET", "/reference-documents/categories")

gen_docs = test("Generated documents", "GET", "/generated-documents/")
if gen_docs:
    g_list = gen_docs if isinstance(gen_docs, list) else gen_docs.get("documents", [])
    print(f"       Generated docs: {len(g_list)}")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 10: Document Generation
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 10: Document Generation ---")

if test_assessment_id:
    suggest = test("Suggest documents", "POST", f"/assessments/{test_assessment_id}/suggest-documents")
    if suggest:
        s_list = suggest if isinstance(suggest, list) else suggest.get("suggestions", suggest.get("documents", []))
        print(f"       Suggestions: {len(s_list)}")

test("Generation jobs", "GET", "/generation-jobs/")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 11: Pricing
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 11: Pricing ---")

test("Pricing benchmark", "GET", "/pricing-v3/benchmark?line_of_business=cyber&coverage_limit=5000000")
test("Pricing lines", "GET", "/pricing-v3/lines")
test("Pricing territories", "GET", "/pricing-v3/territories")
test("Pricing factors", "GET", "/pricing-v3/factors")
test("Market trends", "GET", "/pricing-v3/market-trends")

# Technical price calculation - only test with a real assessment_id
if test_assessment_id:
    tech_price = test("Technical price", "POST", "/pricing/technical", json_body={
        "assessment_id": str(test_assessment_id),
        "class_of_business": "cyber",
        "limit_of_liability": 5000000,
        "territory": "United Kingdom",
        "currency": "GBP",
    })
    if tech_price:
        print(f"       Price: {json.dumps(tech_price)[:100]}")
else:
    print("  [SKIP] Technical price: no assessment_id available")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 12: Lloyd's Market
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 12: Lloyd's Market ---")

syndicates = test("List syndicates", "GET", "/syndicates")
if syndicates:
    s_list = syndicates if isinstance(syndicates, list) else syndicates.get("syndicates", [])
    print(f"       Syndicates: {len(s_list)}")

placements = test("List placements", "GET", "/placements/")
if placements:
    p_list = placements if isinstance(placements, list) else placements.get("placements", placements.get("items", []))
    print(f"       Placements: {len(p_list)}")

# UMR
test("Generate UMR", "POST", "/umr/generate", expected_status=201, json_body={
    "syndicate_number": "1234",
    "risk_type": "cyber",
    "year": 2026,
})

# ═══════════════════════════════════════════════════════════════════════
# PHASE 13: Compliance & Sanctions
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 13: Compliance & Sanctions ---")

test("Screening levels", "GET", "/sanctions/levels")

test("Quick sanctions screen", "POST", "/sanctions/quick-screen", json_body={
    "name": "Test Corp Ltd",
    "entity_type": "company",
})

# ═══════════════════════════════════════════════════════════════════════
# PHASE 14: Teams & Permissions
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 14: Teams & Permissions ---")

test("My permissions", "GET", "/teams/permissions/me")
test("List roles", "GET", "/teams/roles")
test("List teams", "GET", "/teams/teams")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 15: Language
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 15: Language ---")

test("Supported languages", "GET", "/language/supported")
test("User language preference", "GET", "/language/user/preference")
test("Terminology", "GET", "/language/terminology")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 16: Loss Runs & Claims
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 16: Loss Runs & Claims ---")

test("List claims", "GET", "/claims/")
test("Claims stats", "GET", "/claims/stats")

if test_assessment_id:
    test("Loss runs for assessment", "GET", f"/loss-runs/{test_assessment_id}")
    test("Loss run summary", "GET", f"/loss-runs/{test_assessment_id}/summary")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 17: ClaimSense
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 17: ClaimSense ---")

test("ClaimSense benchmark", "GET", "/claimsense/benchmark?policy_type=CY")
test("ClaimSense policy types", "GET", "/claimsense/policy-types")
test("ClaimSense states", "GET", "/claimsense/states")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 18: Analysis modes
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 18: Analysis ---")

modes = test("Analysis modes", "GET", "/analysis/modes")
if modes:
    mode_list = modes if isinstance(modes, list) else modes.get("modes", [])
    print(f"       Modes: {len(mode_list)}")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 19: Upload Sessions
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 19: Upload Sessions ---")

session = test("Create upload session", "POST", "/upload-sessions/create", json_body={})
if session:
    upload_token = session.get("token", session.get("upload_token", "?"))
    print(f"       Token: {upload_token}")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 20: Admin & RAG
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 20: Admin ---")

test("Admin health", "GET", "/admin/health")
rag = test("RAG status", "GET", "/admin/rag-status")
if rag:
    print(f"       RAG: {json.dumps(rag)[:150]}")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 21: Extraction
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 21: Extraction ---")

test("Extraction patterns", "GET", "/extraction/patterns")
test("Extraction accuracy", "GET", "/extraction/metrics/accuracy")
test("Training stats", "GET", "/extraction/training/stats")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 22: Cleanup — delete test assessment
# ═══════════════════════════════════════════════════════════════════════
print("\n--- PHASE 22: Cleanup ---")

if new_assessment_id:
    test(f"Delete test assessment", "DELETE", f"/assessments/{new_assessment_id}", expected_status=204)

# ═══════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
passed = sum(1 for r in results if r["pass"])
failed = sum(1 for r in results if not r["pass"])
total = len(results)
pct = (passed / total * 100) if total > 0 else 0
print(f"RESULTS: {passed}/{total} passed ({pct:.0f}%), {failed} failed")
print("=" * 70)

if failed > 0:
    print("\nFailed tests:")
    for r in results:
        if not r["pass"]:
            print(f"  [FAIL] {r['name']}: status={r['status']}")

# Categorize failures
if failed > 0:
    print("\nFailure analysis:")
    server_errors = [r for r in results if not r["pass"] and r["status"] == 500]
    client_errors = [r for r in results if not r["pass"] and isinstance(r["status"], int) and 400 <= r["status"] < 500]
    other_errors = [r for r in results if not r["pass"] and r["status"] not in [500] and (not isinstance(r["status"], int) or r["status"] < 400)]

    if server_errors:
        print(f"  Server errors (500): {len(server_errors)} — need backend fix + deploy")
        for r in server_errors:
            print(f"    - {r['name']}")
    if client_errors:
        print(f"  Client errors (4xx): {len(client_errors)} — need request fix")
        for r in client_errors:
            print(f"    - {r['name']} ({r['status']})")
    if other_errors:
        print(f"  Other errors: {len(other_errors)}")
        for r in other_errors:
            print(f"    - {r['name']} ({r['status']})")

print(f"\nDone.")
sys.exit(0 if failed == 0 else 1)
