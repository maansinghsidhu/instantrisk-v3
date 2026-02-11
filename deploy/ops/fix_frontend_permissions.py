"""Fix S3 bucket policy and CloudFront CSP for frontend"""
import boto3
import json

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

s3 = session.client('s3')
cloudfront = session.client('cloudfront')

BUCKET = "instantrisk-frontend-995306061991"
DISTRIBUTION_ID = "E3UH4JXGMSZPC5"  # Will find dynamically

print("=" * 60)
print("STEP 1: Check current S3 bucket settings")
print("=" * 60)

# Check current bucket policy
try:
    policy = s3.get_bucket_policy(Bucket=BUCKET)
    print("Current policy:")
    print(json.dumps(json.loads(policy['Policy']), indent=2))
except Exception as e:
    print(f"No policy or error: {e}")

# Check public access block
try:
    pab = s3.get_public_access_block(Bucket=BUCKET)
    print("\nPublic Access Block:")
    print(json.dumps(pab['PublicAccessBlockConfiguration'], indent=2))
except Exception as e:
    print(f"No public access block: {e}")

print("\n" + "=" * 60)
print("STEP 2: Find CloudFront distribution")
print("=" * 60)

# Find CloudFront distribution
distributions = cloudfront.list_distributions()
cf_dist = None
for dist in distributions.get('DistributionList', {}).get('Items', []):
    for origin in dist.get('Origins', {}).get('Items', []):
        if BUCKET in origin.get('DomainName', ''):
            cf_dist = dist
            DISTRIBUTION_ID = dist['Id']
            print(f"Found distribution: {dist['Id']}")
            print(f"  Domain: {dist['DomainName']}")
            print(f"  OAI: {origin.get('S3OriginConfig', {}).get('OriginAccessIdentity', 'None')}")
            break

if not cf_dist:
    print("CloudFront distribution not found!")
    exit(1)

print("\n" + "=" * 60)
print("STEP 3: Update S3 bucket policy for CloudFront OAC/OAI")
print("=" * 60)

# Get the CloudFront OAI
oai_id = None
for origin in cf_dist.get('Origins', {}).get('Items', []):
    oai_path = origin.get('S3OriginConfig', {}).get('OriginAccessIdentity', '')
    if oai_path:
        oai_id = oai_path.split('/')[-1]
        print(f"OAI ID: {oai_id}")

# Create bucket policy allowing CloudFront
bucket_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCloudFrontAccess",
            "Effect": "Allow",
            "Principal": {
                "Service": "cloudfront.amazonaws.com"
            },
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{BUCKET}/*",
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn": f"arn:aws:cloudfront::995306061991:distribution/{DISTRIBUTION_ID}"
                }
            }
        }
    ]
}

# If OAI exists, add that too
if oai_id:
    bucket_policy["Statement"].append({
        "Sid": "AllowCloudFrontOAI",
        "Effect": "Allow",
        "Principal": {
            "AWS": f"arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity {oai_id}"
        },
        "Action": "s3:GetObject",
        "Resource": f"arn:aws:s3:::{BUCKET}/*"
    })

try:
    s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps(bucket_policy))
    print("Bucket policy updated!")
    print(json.dumps(bucket_policy, indent=2))
except Exception as e:
    print(f"Error updating policy: {e}")

print("\n" + "=" * 60)
print("STEP 4: Check and fix response headers policy (CSP)")
print("=" * 60)

# Get distribution config
dist_config = cloudfront.get_distribution_config(Id=DISTRIBUTION_ID)
config = dist_config['DistributionConfig']
etag = dist_config['ETag']

# Check default cache behavior for response headers policy
default_behavior = config.get('DefaultCacheBehavior', {})
response_headers_policy_id = default_behavior.get('ResponseHeadersPolicyId')

if response_headers_policy_id:
    print(f"Response headers policy: {response_headers_policy_id}")
    try:
        policy = cloudfront.get_response_headers_policy(Id=response_headers_policy_id)
        policy_config = policy['ResponseHeadersPolicy']['ResponseHeadersPolicyConfig']
        print(f"Policy name: {policy_config.get('Name')}")

        # Check security headers
        security_headers = policy_config.get('SecurityHeadersConfig', {})
        csp = security_headers.get('ContentSecurityPolicy', {})
        if csp:
            print(f"Current CSP: {csp.get('ContentSecurityPolicy', 'Not set')}")
    except Exception as e:
        print(f"Error getting policy: {e}")
else:
    print("No response headers policy set")

print("\n" + "=" * 60)
print("STEP 5: Create/Update response headers policy with relaxed CSP")
print("=" * 60)

# Create a new response headers policy with relaxed CSP for fonts
new_policy_name = "InstantRisk-Frontend-Headers"

# Relaxed CSP that allows Google Fonts
relaxed_csp = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "style-src-elem 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com "
    "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com "
    "https://*.amazonaws.com wss:; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "base-uri 'self';"
)

new_policy_config = {
    'Name': new_policy_name,
    'Comment': 'Headers for InstantRisk Flutter frontend',
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
        }
    }
}

# Try to create or update the policy
try:
    # First try to find existing policy
    policies = cloudfront.list_response_headers_policies()
    existing_policy_id = None
    for p in policies.get('ResponseHeadersPolicyList', {}).get('Items', []):
        if p['ResponseHeadersPolicy']['ResponseHeadersPolicyConfig']['Name'] == new_policy_name:
            existing_policy_id = p['ResponseHeadersPolicy']['Id']
            break

    if existing_policy_id:
        # Update existing
        existing = cloudfront.get_response_headers_policy(Id=existing_policy_id)
        cloudfront.update_response_headers_policy(
            Id=existing_policy_id,
            ResponseHeadersPolicyConfig=new_policy_config,
            IfMatch=existing['ETag']
        )
        print(f"Updated policy: {existing_policy_id}")
        new_policy_id = existing_policy_id
    else:
        # Create new
        result = cloudfront.create_response_headers_policy(
            ResponseHeadersPolicyConfig=new_policy_config
        )
        new_policy_id = result['ResponseHeadersPolicy']['Id']
        print(f"Created policy: {new_policy_id}")

except Exception as e:
    print(f"Error with policy: {e}")
    new_policy_id = None

print("\n" + "=" * 60)
print("STEP 6: Update CloudFront distribution with new policy")
print("=" * 60)

if new_policy_id:
    try:
        # Get fresh config
        dist_config = cloudfront.get_distribution_config(Id=DISTRIBUTION_ID)
        config = dist_config['DistributionConfig']
        etag = dist_config['ETag']

        # Update default cache behavior
        config['DefaultCacheBehavior']['ResponseHeadersPolicyId'] = new_policy_id

        cloudfront.update_distribution(
            Id=DISTRIBUTION_ID,
            DistributionConfig=config,
            IfMatch=etag
        )
        print("Distribution updated with new response headers policy!")
    except Exception as e:
        print(f"Error updating distribution: {e}")

print("\n" + "=" * 60)
print("STEP 7: Invalidate CloudFront cache")
print("=" * 60)

try:
    import time
    invalidation = cloudfront.create_invalidation(
        DistributionId=DISTRIBUTION_ID,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/*']
            },
            'CallerReference': str(int(time.time()))
        }
    )
    print(f"Invalidation created: {invalidation['Invalidation']['Id']}")
except Exception as e:
    print(f"Error creating invalidation: {e}")

print("\n" + "=" * 60)
print("DONE!")
print("=" * 60)
print("Wait 2-3 minutes for CloudFront to propagate, then refresh the page.")
print("Frontend: https://d2f065h47nuk0c.cloudfront.net")
