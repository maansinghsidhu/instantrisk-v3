"""
Check EC2 backend users - try different credentials
"""
import urllib.request
import urllib.error
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

EC2_URL = "http://35.169.106.135"
API_BASE = f"{EC2_URL}/api/v1"

def login(email, password):
    """Login and return result"""
    url = f"{API_BASE}/auth/login"
    data = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            result = json.loads(resp.read().decode())
            return "OK", result
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        return f"{e.code}", detail
    except Exception as e:
        return "ERROR", str(e)

# First check health
print("=" * 60)
print(f"Checking EC2 backend at {EC2_URL}")
print("=" * 60)

try:
    with urllib.request.urlopen(f"{EC2_URL}/health", timeout=10, context=ctx) as resp:
        health = resp.read().decode()
        print(f"Health: {resp.status} OK")
        print(f"  {health[:200]}")
except Exception as e:
    print(f"Health check failed: {e}")

print("\n" + "=" * 60)
print("Testing login credentials...")
print("=" * 60)

# Test various email/password combinations
test_creds = [
    # Demo user with different passwords
    ("demo@instantrisk.com", "Demo2026pass"),
    ("demo@instantrisk.com", "demo"),
    ("demo@instantrisk.com", "Demo123!"),
    ("demo@instantrisk.com", "password"),
    ("demo@instantrisk.com", "demo2026"),

    # Admin variants
    ("admin@instantrisk.com", "Admin2026pass"),
    ("admin@instantrisk.com", "admin"),
    ("admin@instantrisk.com", "Admin123!"),

    # Test user
    ("test@instantrisk.com", "test"),
    ("test@instantrisk.com", "Test123!"),
    ("test@instantrisk.com", "Test2026pass"),

    # Underwriter
    ("underwriter@instantrisk.com", "Underwriter2026pass"),
    ("underwriter@instantrisk.com", "underwriter"),
]

for email, pwd in test_creds:
    status, result = login(email, pwd)
    if status == "OK":
        user = result.get("user", {})
        print(f"SUCCESS: {email} / {pwd}")
        print(f"  User: {user.get('email')} - role={user.get('role')}")

        # Get subscription
        token = result.get("access_token")
        if token:
            try:
                req = urllib.request.Request(
                    f"{API_BASE}/subscription",
                    headers={"Authorization": f"Bearer {token}"}
                )
                with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                    sub = json.loads(resp.read().decode())
                    print(f"  Subscription: tier={sub.get('tier')}, status={sub.get('status')}")
            except Exception as e:
                print(f"  Subscription: error - {e}")
    else:
        # Only print first failure for each email
        pass

print("\n" + "=" * 60)
print("Checking registration endpoint...")
print("=" * 60)

# Try to register a new user to see if it works
test_user = {
    "email": "testuser123@instantrisk.com",
    "password": "TestUser123!",
    "full_name": "Test User 123",
    "role": "broker"
}

url = f"{API_BASE}/auth/register"
data = json.dumps(test_user).encode()
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        result = json.loads(resp.read().decode())
        print(f"Registration: {resp.status}")
        print(f"  Result: {result}")
except urllib.error.HTTPError as e:
    detail = e.read().decode()
    if "already registered" in detail.lower():
        print(f"Registration: User already exists")
    elif "rate" in detail.lower():
        print(f"Registration: Rate limited")
    else:
        print(f"Registration: {e.code} - {detail[:200]}")
except Exception as e:
    print(f"Registration error: {e}")
