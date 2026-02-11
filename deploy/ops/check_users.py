"""Check existing users in RDS database"""
import boto3
import requests

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

# Check EC2 backend for users
EC2_URL = "http://35.169.106.135"
ALB_URL = "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com"

print("=" * 60)
print("Checking EC2 Backend for User List API")
print("=" * 60)

# Try to find a users endpoint on EC2
endpoints_to_try = [
    "/api/v1/users",
    "/api/users",
    "/users",
    "/api/v1/admin/users",
]

for endpoint in endpoints_to_try:
    try:
        resp = requests.get(f"{EC2_URL}{endpoint}", timeout=10)
        print(f"EC2 {endpoint}: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  Response: {resp.text[:500]}")
    except Exception as e:
        print(f"EC2 {endpoint}: ERROR")

print("\n" + "=" * 60)
print("Checking ALB (Fargate) Backend")
print("=" * 60)

for endpoint in endpoints_to_try:
    try:
        resp = requests.get(f"{ALB_URL}{endpoint}", timeout=10)
        print(f"ALB {endpoint}: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  Response: {resp.text[:500]}")
    except Exception as e:
        print(f"ALB {endpoint}: ERROR")

print("\n" + "=" * 60)
print("Try logging in with different test accounts")
print("=" * 60)

# Common test accounts to try
test_accounts = [
    ("demo@instantrisk.com", "Demo2026pass"),
    ("admin@instantrisk.com", "Admin2026pass"),
    ("test@instantrisk.com", "Test2026pass"),
    ("basic@instantrisk.com", "Basic2026pass"),
    ("trial@instantrisk.com", "Trial2026pass"),
    ("premium@instantrisk.com", "Premium2026pass"),
    ("analyst@instantrisk.com", "Analyst2026pass"),
    ("underwriter@instantrisk.com", "Underwriter2026pass"),
]

for email, password in test_accounts:
    try:
        resp = requests.post(
            f"{ALB_URL}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"  {email}: OK")
        else:
            print(f"  {email}: {resp.status_code}")
    except Exception as e:
        print(f"  {email}: ERROR")

print("\nDone!")
