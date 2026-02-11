"""
Fix CloudFront to proxy /api/* requests to ALB.
Adds ALB as second origin and creates cache behavior for API paths.
"""
import boto3
import json
import time
import urllib.request
import urllib.error

# AWS Credentials
AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_SESSION_TOKEN = os.environ.get('AWS_SESSION_TOKEN', '')

AWS_REGION = "us-east-1"
DISTRIBUTION_ID = "E27KXSCZQ10BRJ"
ALB_DOMAIN = "instantrisk-alb-307384033.us-east-1.elb.amazonaws.com"
CLOUDFRONT_URL = "https://d2f065h47nuk0c.cloudfront.net"

def create_session():
    return boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        aws_session_token=AWS_SESSION_TOKEN,
        region_name=AWS_REGION
    )


def update_cloudfront_with_alb_origin(session):
    """Add ALB as origin and /api/* cache behavior to CloudFront."""
    cf = session.client('cloudfront')

    # Get current distribution config
    print("Getting current CloudFront distribution config...")
    response = cf.get_distribution_config(Id=DISTRIBUTION_ID)
    config = response['DistributionConfig']
    etag = response['ETag']

    # Check if ALB origin already exists
    alb_origin_id = 'instantrisk-alb-origin'
    origins = config['Origins']['Items']
    origin_ids = [o['Id'] for o in origins]

    if alb_origin_id in origin_ids:
        print(f"ALB origin '{alb_origin_id}' already exists")
    else:
        print(f"Adding ALB origin: {ALB_DOMAIN}")
        # Add ALB as a new origin with all required fields
        alb_origin = {
            'Id': alb_origin_id,
            'DomainName': ALB_DOMAIN,
            'OriginPath': '',
            'CustomHeaders': {'Quantity': 0},
            'CustomOriginConfig': {
                'HTTPPort': 80,
                'HTTPSPort': 443,
                'OriginProtocolPolicy': 'http-only',
                'OriginSslProtocols': {'Quantity': 1, 'Items': ['TLSv1.2']},
                'OriginReadTimeout': 60,
                'OriginKeepaliveTimeout': 5
            },
            'ConnectionAttempts': 3,
            'ConnectionTimeout': 10,
            'OriginShield': {'Enabled': False}
        }
        origins.append(alb_origin)
        config['Origins']['Quantity'] = len(origins)

    # Check if /api/* cache behavior exists
    cache_behaviors = config.get('CacheBehaviors', {'Quantity': 0, 'Items': []})
    if cache_behaviors['Quantity'] == 0:
        cache_behaviors = {'Quantity': 0, 'Items': []}
        config['CacheBehaviors'] = cache_behaviors

    api_pattern_exists = any(
        cb.get('PathPattern') == '/api/*'
        for cb in cache_behaviors.get('Items', [])
    )

    if api_pattern_exists:
        print("API cache behavior '/api/*' already exists")
    else:
        print("Adding cache behavior for /api/*")
        # Create cache behavior for API with ALL required fields
        api_behavior = {
            'PathPattern': '/api/*',
            'TargetOriginId': alb_origin_id,
            'ViewerProtocolPolicy': 'https-only',
            'AllowedMethods': {
                'Quantity': 7,
                'Items': ['GET', 'HEAD', 'OPTIONS', 'PUT', 'POST', 'PATCH', 'DELETE'],
                'CachedMethods': {'Quantity': 2, 'Items': ['GET', 'HEAD']}
            },
            'SmoothStreaming': False,
            'Compress': False,
            'TrustedSigners': {'Enabled': False, 'Quantity': 0},
            'TrustedKeyGroups': {'Enabled': False, 'Quantity': 0},
            'LambdaFunctionAssociations': {'Quantity': 0},
            'FunctionAssociations': {'Quantity': 0},
            'FieldLevelEncryptionId': '',
            'GrpcConfig': {'Enabled': False},
            # Use ForwardedValues for API - forward everything
            'ForwardedValues': {
                'QueryString': True,
                'Cookies': {'Forward': 'all'},
                'Headers': {
                    'Quantity': 4,
                    'Items': ['Authorization', 'Content-Type', 'Accept', 'Origin']
                },
                'QueryStringCacheKeys': {'Quantity': 0}
            },
            'MinTTL': 0,
            'DefaultTTL': 0,
            'MaxTTL': 0
        }

        if 'Items' not in cache_behaviors:
            cache_behaviors['Items'] = []
        cache_behaviors['Items'].append(api_behavior)
        cache_behaviors['Quantity'] = len(cache_behaviors['Items'])
        config['CacheBehaviors'] = cache_behaviors

    # Update the distribution
    print("Updating CloudFront distribution...")
    try:
        cf.update_distribution(
            Id=DISTRIBUTION_ID,
            DistributionConfig=config,
            IfMatch=etag
        )
        print("CloudFront distribution updated successfully!")
        return True
    except Exception as e:
        print(f"Error updating distribution: {e}")
        return False


def wait_for_deployment(session):
    """Wait for CloudFront distribution to deploy."""
    cf = session.client('cloudfront')
    print("\nWaiting for CloudFront deployment...")

    for i in range(30):  # Up to 15 minutes
        response = cf.get_distribution(Id=DISTRIBUTION_ID)
        status = response['Distribution']['Status']
        print(f"  Status: {status}")

        if status == 'Deployed':
            print("CloudFront deployment complete!")
            return True

        time.sleep(30)

    print("Deployment timed out")
    return False


def verify_api_via_cloudfront():
    """Verify that API calls work through CloudFront."""
    print("\n" + "=" * 60)
    print("VERIFICATION: Testing API through CloudFront")
    print("=" * 60)

    # Test health endpoint
    health_url = f"{CLOUDFRONT_URL}/api/v1/health/live"
    print(f"\nTest 1: GET {health_url}")

    try:
        req = urllib.request.Request(health_url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode('utf-8')
            print(f"  Status: {resp.status}")
            print(f"  Response: {data}")
            if resp.status == 200:
                print("  PASS: Health endpoint works!")
            else:
                print("  FAIL: Unexpected status")
                return False
    except urllib.error.HTTPError as e:
        print(f"  FAIL: HTTP {e.code} - {e.reason}")
        return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

    # Test login endpoint
    login_url = f"{CLOUDFRONT_URL}/api/v1/auth/login"
    print(f"\nTest 2: POST {login_url} (auth test)")

    try:
        login_data = json.dumps({
            "email": "demo@instantrisk.com",
            "password": "Demo2026pass"
        }).encode('utf-8')

        req = urllib.request.Request(
            login_url,
            data=login_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode('utf-8')
            print(f"  Status: {resp.status}")
            result = json.loads(data)
            if 'access_token' in result:
                print(f"  User: {result.get('user', {}).get('email', 'unknown')}")
                print("  PASS: Login works through CloudFront!")
                return True
            else:
                print(f"  Response: {data[:200]}")
                print("  FAIL: No access token in response")
                return False
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else ''
        print(f"  FAIL: HTTP {e.code} - {e.reason}")
        print(f"  Body: {body[:200]}")
        return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def main():
    session = create_session()

    # Verify credentials
    try:
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"Authenticated as: {identity['Arn']}")
    except Exception as e:
        print(f"Credential error: {e}")
        return

    # Update CloudFront
    if not update_cloudfront_with_alb_origin(session):
        print("Failed to update CloudFront")
        return

    # Wait for deployment
    if not wait_for_deployment(session):
        print("Deployment did not complete in time - may still be propagating")
        # Continue to verify anyway

    # Verify the fix
    if verify_api_via_cloudfront():
        print("\n" + "=" * 60)
        print("SUCCESS! Mixed Content issue is FIXED")
        print("=" * 60)
        print(f"\nFrontend URL: {CLOUDFRONT_URL}")
        print("API calls now go through CloudFront (HTTPS) -> ALB (HTTP)")
        print("\nTest users:")
        print("  trial.user@test.com / TestPass123 (TRIAL)")
        print("  basic.user@test.com / TestPass123 (BASIC)")
        print("  premium.user@test.com / TestPass123 (PREMIUM)")
        print("  demo@instantrisk.com / Demo2026pass (PREMIUM)")
    else:
        print("\n" + "=" * 60)
        print("VERIFICATION FAILED")
        print("=" * 60)
        print("The CloudFront update may still be propagating.")
        print("Wait a few minutes and try accessing the site.")


if __name__ == "__main__":
    main()
