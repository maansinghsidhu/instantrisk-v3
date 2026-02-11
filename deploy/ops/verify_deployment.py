import requests
import json

alb_url = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com"

print("=" * 60)
print("VERIFYING BACKEND DEPLOYMENT")
print("=" * 60)

# Check root
print("\n1. Root endpoint:")
try:
    resp = requests.get(f"{alb_url}/", timeout=10)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.json()}")
except Exception as e:
    print(f"  Error: {e}")

# Check docs
print("\n2. API Docs:")
try:
    resp = requests.get(f"{alb_url}/docs", timeout=10)
    print(f"  Status: {resp.status_code}")
    print(f"  Size: {len(resp.text)} bytes")
except Exception as e:
    print(f"  Error: {e}")

# Check assessments endpoint (NEW!)
print("\n3. Assessments endpoint (NEW):")
try:
    resp = requests.get(f"{alb_url}/api/v1/assessments", timeout=10)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 401:
        print("  (Requires auth - endpoint exists!)")
    else:
        print(f"  Response: {resp.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")

# Check OpenAPI spec for assessments
print("\n4. OpenAPI Spec check:")
try:
    resp = requests.get(f"{alb_url}/openapi.json", timeout=10)
    if resp.status_code == 200:
        spec = resp.json()
        paths = list(spec.get('paths', {}).keys())
        assessment_paths = [p for p in paths if 'assessment' in p.lower()]
        print(f"  Total endpoints: {len(paths)}")
        print(f"  Assessment endpoints: {assessment_paths}")
    else:
        print(f"  Status: {resp.status_code}")
except Exception as e:
    print(f"  Error: {e}")

# Test login
print("\n5. Login test:")
try:
    resp = requests.post(
        f"{alb_url}/api/v1/auth/login",
        json={"email": "demo@instantrisk.com", "password": "Demo2026pass"},
        timeout=10
    )
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        token = resp.json().get('access_token', '')[:50]
        print(f"  Token: {token}...")
except Exception as e:
    print(f"  Error: {e}")

# Check CloudFront frontend
print("\n6. CloudFront Frontend:")
try:
    resp = requests.get("https://d2f065h47nuk0c.cloudfront.net/", timeout=10)
    print(f"  Status: {resp.status_code}")
    if "InstantRisk" in resp.text:
        print("  Contains 'InstantRisk' - CORRECT frontend!")
    else:
        print("  Missing 'InstantRisk' - wrong frontend")
except Exception as e:
    print(f"  Error: {e}")

print("\nDone!")
