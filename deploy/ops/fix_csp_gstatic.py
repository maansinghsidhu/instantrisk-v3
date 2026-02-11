"""Fix CSP to allow www.gstatic.com for Flutter canvaskit"""
import boto3
import time

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

cloudfront = session.client('cloudfront')

CF_DIST_ID = "E27KXSCZQ10BRJ"
POLICY_ID = "67510994-3bc4-4f82-8c5f-a7f2ce823da2"

# Updated CSP that allows www.gstatic.com for Flutter canvaskit
relaxed_csp = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.gstatic.com; "
    "script-src-elem 'self' 'unsafe-inline' https://www.gstatic.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "style-src-elem 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self' https://www.gstatic.com https://fonts.gstatic.com https://fonts.googleapis.com "
    "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com "
    "https://*.amazonaws.com wss:; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self';"
)

print("=" * 60)
print("Updating CSP to allow www.gstatic.com")
print("=" * 60)

# Create a completely new policy config with all required fields
new_config = {
    'Name': 'InstantRisk-Frontend-Headers',
    'Comment': 'Headers for InstantRisk Flutter frontend with full gstatic support',
    'SecurityHeadersConfig': {
        'XSSProtection': {
            'Override': True,
            'Protection': True,
            'ModeBlock': True
        },
        'FrameOptions': {
            'Override': True,
            'FrameOption': 'DENY'
        },
        'ContentTypeOptions': {
            'Override': True
        },
        'StrictTransportSecurity': {
            'Override': True,
            'IncludeSubdomains': True,
            'AccessControlMaxAgeSec': 31536000
        },
        'ContentSecurityPolicy': {
            'Override': True,
            'ContentSecurityPolicy': relaxed_csp
        },
        'ReferrerPolicy': {
            'Override': True,
            'ReferrerPolicy': 'strict-origin-when-cross-origin'
        }
    }
}

try:
    # Get current ETag
    policy = cloudfront.get_response_headers_policy(Id=POLICY_ID)
    etag = policy['ETag']

    print(f"Updating policy: {POLICY_ID}")

    # Update policy with complete config
    cloudfront.update_response_headers_policy(
        Id=POLICY_ID,
        ResponseHeadersPolicyConfig=new_config,
        IfMatch=etag
    )
    print("Policy updated successfully!")
    print(f"\nNew CSP includes: www.gstatic.com")

except Exception as e:
    print(f"Error updating policy: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Invalidating CloudFront cache")
print("=" * 60)

try:
    resp = cloudfront.create_invalidation(
        DistributionId=CF_DIST_ID,
        InvalidationBatch={
            'Paths': {'Quantity': 1, 'Items': ['/*']},
            'CallerReference': str(int(time.time()))
        }
    )
    print(f"Invalidation: {resp['Invalidation']['Id']}")
except Exception as e:
    print(f"Error: {e}")

print("\nDone! Wait 1-2 minutes and refresh the page.")
