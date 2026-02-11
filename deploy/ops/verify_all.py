import requests
import time

print("=" * 60)
print("FULL SYSTEM VERIFICATION")
print("=" * 60)

# Backend
alb = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com"
cf = "https://d2f065h47nuk0c.cloudfront.net"

print("\n1. BACKEND STATUS")
try:
    resp = requests.get(f"{alb}/", timeout=10)
    print(f"  Root: {resp.status_code} - {resp.json()}")
except Exception as e:
    print(f"  Error: {e}")

print("\n2. BACKEND LOGIN")
try:
    resp = requests.post(
        f"{alb}/api/v1/auth/login",
        json={"email": "demo@instantrisk.com", "password": "Demo2026pass"},
        timeout=10
    )
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        token = resp.json().get('access_token', '')[:50]
        print(f"  Token: {token}...")
        print("  LOGIN: OK")
except Exception as e:
    print(f"  Error: {e}")

print("\n3. FRONTEND STATUS")
try:
    resp = requests.get(cf, timeout=10)
    print(f"  Status: {resp.status_code}")
    if "InstantRisk" in resp.text:
        print("  Contains 'InstantRisk': YES")
except Exception as e:
    print(f"  Error: {e}")

print("\n4. FRONTEND ASSETS (missing ones)")
assets = [
    "assets/assets/fonts/Inter-Regular.ttf",
    "assets/assets/images/logo_icon.png",
]
for asset in assets:
    try:
        resp = requests.head(f"{cf}/{asset}", timeout=10)
        size = resp.headers.get('content-length', '?')
        print(f"  {asset}: {resp.status_code} ({size} bytes)")
    except Exception as e:
        print(f"  {asset}: ERROR - {e}")

print("\n5. API ENDPOINTS")
try:
    resp = requests.get(f"{alb}/openapi.json", timeout=10)
    if resp.status_code == 200:
        spec = resp.json()
        paths = list(spec.get('paths', {}).keys())
        print(f"  Total endpoints: {len(paths)}")
        assessment_paths = [p for p in paths if 'assessment' in p.lower()]
        print(f"  Assessment endpoints: {len(assessment_paths)}")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Backend:  {alb}")
print(f"Frontend: {cf}")
print("Login:    demo@instantrisk.com / Demo2026pass")
