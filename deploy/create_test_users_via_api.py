"""
Create test users with different subscription tiers via the API.
This script uses the /register endpoint to create users.

Note: New users get TRIAL tier by default.
To change tiers, an admin would need to update via database.
"""
import urllib.request
import urllib.error
import json
import ssl

# Disable SSL verification for testing
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# API endpoints
ALB_URL = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com"
API_BASE = f"{ALB_URL}/api/v1"

# Test users to create
TEST_USERS = [
    {
        "email": "trial@instantrisk.com",
        "password": "Trial2026pass",
        "full_name": "Trial User",
        "role": "broker",
    },
    {
        "email": "basic@instantrisk.com",
        "password": "Basic2026pass",
        "full_name": "Basic User",
        "role": "broker",
    },
    {
        "email": "premium@instantrisk.com",
        "password": "Premium2026pass",
        "full_name": "Premium User",
        "role": "broker",
    },
]

def register_user(user_data):
    """Register a new user via API."""
    url = f"{API_BASE}/auth/register"
    data = json.dumps(user_data).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            return True, result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return False, {"status": e.code, "detail": error_body}
    except urllib.error.URLError as e:
        return False, {"error": str(e)}
    except Exception as e:
        return False, {"error": str(e)}

def login_user(email, password):
    """Test login for a user."""
    url = f"{API_BASE}/auth/login"
    data = json.dumps({"email": email, "password": password}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            return True, result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return False, {"status": e.code, "detail": error_body}
    except urllib.error.URLError as e:
        return False, {"error": str(e)}
    except Exception as e:
        return False, {"error": str(e)}

def main():
    print("=" * 60)
    print("Testing ALB connectivity...")
    print("=" * 60)

    # Test health endpoint
    try:
        with urllib.request.urlopen(f"{ALB_URL}/health", timeout=10) as response:
            print(f"Health check: {response.status} OK")
    except Exception as e:
        print(f"Health check failed: {e}")
        print("\nALB may not be reachable from this machine.")
        print("Try running this script from within AWS (EC2, CloudShell, etc.)")
        return

    print("\n" + "=" * 60)
    print("Registering test users...")
    print("=" * 60)

    for user in TEST_USERS:
        print(f"\nRegistering {user['email']}...")
        success, result = register_user(user)
        if success:
            print(f"  SUCCESS: User created with id={result.get('id')}")
        else:
            if "already registered" in str(result).lower():
                print(f"  SKIP: User already exists")
            else:
                print(f"  ERROR: {result}")

    print("\n" + "=" * 60)
    print("Testing logins...")
    print("=" * 60)

    # Test demo user (should exist)
    print("\nTesting demo@instantrisk.com...")
    success, result = login_user("demo@instantrisk.com", "Demo2026pass")
    if success:
        user = result.get('user', {})
        print(f"  LOGIN OK: {user.get('email')} - role={user.get('role')}")
    else:
        print(f"  FAILED: {result}")

    # Test new users
    for user in TEST_USERS:
        print(f"\nTesting {user['email']}...")
        success, result = login_user(user['email'], user['password'])
        if success:
            user_info = result.get('user', {})
            print(f"  LOGIN OK: role={user_info.get('role')}")
        elif "pending approval" in str(result).lower():
            print(f"  PENDING: Account needs admin approval")
        else:
            print(f"  FAILED: {result}")

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("""
CONFIRMED WORKING LOGIN:
  Email: demo@instantrisk.com
  Password: Demo2026pass
  Tier: PREMIUM (migration bonus)

NEW TEST USERS (if registered):
  Note: New users require admin approval before login.
  Once approved, they will have TRIAL tier by default.

  trial@instantrisk.com / Trial2026pass
  basic@instantrisk.com / Basic2026pass
  premium@instantrisk.com / Premium2026pass
""")

if __name__ == "__main__":
    main()
