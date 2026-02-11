import boto3
import requests

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

print("=" * 60)
print("EC2 BACKEND API")
print("=" * 60)
try:
    resp = requests.get("http://35.169.106.135:8000/", timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("FARGATE BACKEND API (via ALB)")
print("=" * 60)
try:
    resp = requests.get("http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com/", timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("EC2 BACKEND ENDPOINTS")
print("=" * 60)
try:
    resp = requests.get("http://35.169.106.135:8000/docs", timeout=10)
    print(f"Docs page: {resp.status_code} ({len(resp.text)} bytes)")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("FARGATE BACKEND ENDPOINTS")
print("=" * 60)
try:
    resp = requests.get("http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com/docs", timeout=10)
    print(f"Docs page: {resp.status_code} ({len(resp.text)} bytes)")
except Exception as e:
    print(f"Error: {e}")

print("\nDone!")
