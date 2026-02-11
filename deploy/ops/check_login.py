import requests
import json

alb_url = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com"

# Try login with full details
print("Testing login...")
try:
    resp = requests.post(
        f"{alb_url}/api/v1/auth/login",
        json={"email": "demo@instantrisk.com", "password": "Demo2026pass"},
        timeout=30
    )
    print(f"Status: {resp.status_code}")
    print(f"Headers: {dict(resp.headers)}")
    print(f"Body: {resp.text}")
except Exception as e:
    print(f"Error: {e}")

# Check health
print("\n\nHealth check:")
try:
    resp = requests.get(f"{alb_url}/api/v1/health/live", timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
