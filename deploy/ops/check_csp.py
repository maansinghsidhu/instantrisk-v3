"""Check CSP and update index.html if needed"""
import boto3
import requests

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

s3 = session.client('s3')
cloudfront = session.client('cloudfront')

BUCKET = "instantrisk-frontend-995306061991"
CF_DIST_ID = "E27KXSCZQ10BRJ"

print("=" * 60)
print("STEP 1: Get current index.html from S3")
print("=" * 60)

try:
    obj = s3.get_object(Bucket=BUCKET, Key="index.html")
    content = obj['Body'].read().decode('utf-8')
    print(f"Length: {len(content)} chars")
    print("\nContent-Security-Policy check:")

    # Look for CSP
    if 'Content-Security-Policy' in content:
        print("  Found CSP meta tag!")
        # Extract CSP line
        for line in content.split('\n'):
            if 'Content-Security-Policy' in line:
                print(f"  {line.strip()}")
    else:
        print("  No CSP meta tag found")

    print("\nGoogle Fonts check:")
    if 'fonts.googleapis.com' in content:
        print("  Uses Google Fonts - these may be blocked by CSP")
        for line in content.split('\n'):
            if 'fonts.googleapis.com' in line or 'fonts.gstatic.com' in line:
                print(f"  {line.strip()}")
    else:
        print("  No Google Fonts references")

except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("STEP 2: Check CloudFront Response Headers")
print("=" * 60)

try:
    # Get response headers config
    dist = cloudfront.get_distribution(Id=CF_DIST_ID)
    cache_behavior = dist['Distribution']['DistributionConfig']['DefaultCacheBehavior']

    if 'ResponseHeadersPolicyId' in cache_behavior:
        policy_id = cache_behavior['ResponseHeadersPolicyId']
        print(f"Response headers policy: {policy_id}")

        # Get policy details
        policy = cloudfront.get_response_headers_policy(Id=policy_id)
        config = policy['ResponseHeadersPolicy']['ResponseHeadersPolicyConfig']
        if 'SecurityHeadersConfig' in config:
            sec = config['SecurityHeadersConfig']
            if 'ContentSecurityPolicy' in sec:
                csp = sec['ContentSecurityPolicy']
                print(f"CloudFront CSP: {csp.get('ContentSecurityPolicy', 'N/A')}")
                print(f"Override: {csp.get('Override', False)}")
    else:
        print("No response headers policy configured")

except Exception as e:
    print(f"CloudFront error: {e}")

print("\n" + "=" * 60)
print("STEP 3: Check actual response headers from CloudFront")
print("=" * 60)

try:
    resp = requests.get("https://d2f065h47nuk0c.cloudfront.net/", timeout=10)
    print(f"Status: {resp.status_code}")
    print("\nResponse headers:")
    for h, v in resp.headers.items():
        if any(x in h.lower() for x in ['security', 'policy', 'csp', 'content-sec']):
            print(f"  {h}: {v}")
except Exception as e:
    print(f"Error: {e}")

print("\nDone!")
