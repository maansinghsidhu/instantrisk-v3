"""Check S3 frontend content and fix permissions"""
import boto3
import json
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
EC2_URL = "http://35.169.106.135"
CF_DISTRIBUTION = "E3RWFCJSQO4OW3"

print("=" * 60)
print("STEP 1: Check current S3 index.html")
print("=" * 60)

try:
    obj = s3.get_object(Bucket=BUCKET, Key="index.html")
    content = obj['Body'].read().decode('utf-8')[:2000]
    print("Current S3 index.html (first 2000 chars):")
    print(content)
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("STEP 2: Check EC2 index.html")
print("=" * 60)

try:
    resp = requests.get(f"{EC2_URL}/", timeout=30)
    print(f"EC2 status: {resp.status_code}")
    print("EC2 index.html (first 2000 chars):")
    print(resp.text[:2000])
except Exception as e:
    print(f"EC2 Error: {e}")

print("\n" + "=" * 60)
print("STEP 3: Fix S3 permissions")
print("=" * 60)

# Remove public access block
try:
    s3.delete_public_access_block(Bucket=BUCKET)
    print("Removed public access block")
except Exception as e:
    print(f"Public access block: {e}")

# Set bucket policy for public read
bucket_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{BUCKET}/*"
        }
    ]
}

try:
    s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps(bucket_policy))
    print("Set public read bucket policy")
except Exception as e:
    print(f"Bucket policy: {e}")

print("\n" + "=" * 60)
print("STEP 4: Copy EC2 frontend to S3")
print("=" * 60)

# Get list of files from EC2
try:
    # First get the main files
    files_to_copy = [
        "index.html",
        "main.dart.js",
        "flutter.js",
        "flutter_bootstrap.js",
        "manifest.json",
        "favicon.png",
        "flutter_service_worker.js",
        "version.json",
        "assets/AssetManifest.json",
        "assets/AssetManifest.bin",
        "assets/FontManifest.json",
        "assets/NOTICES",
        "assets/shaders/ink_sparkle.frag",
        "assets/fonts/MaterialIcons-Regular.otf",
        "canvaskit/canvaskit.js",
        "canvaskit/canvaskit.wasm",
        "canvaskit/skwasm.js",
        "canvaskit/skwasm.wasm",
        "icons/Icon-192.png",
        "icons/Icon-512.png",
        "icons/Icon-maskable-192.png",
        "icons/Icon-maskable-512.png",
    ]

    success = 0
    failed = 0

    for f in files_to_copy:
        url = f"{EC2_URL}/{f}"
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 200:
                content_type = resp.headers.get('Content-Type', 'application/octet-stream')
                # Map extensions
                if f.endswith('.js'):
                    content_type = 'application/javascript'
                elif f.endswith('.html'):
                    content_type = 'text/html'
                elif f.endswith('.json'):
                    content_type = 'application/json'
                elif f.endswith('.png'):
                    content_type = 'image/png'
                elif f.endswith('.wasm'):
                    content_type = 'application/wasm'
                elif f.endswith('.otf'):
                    content_type = 'font/otf'
                elif f.endswith('.ttf'):
                    content_type = 'font/ttf'
                elif f.endswith('.frag'):
                    content_type = 'text/plain'

                s3.put_object(
                    Bucket=BUCKET,
                    Key=f,
                    Body=resp.content,
                    ContentType=content_type,
                )
                print(f"  OK: {f}")
                success += 1
            else:
                print(f"  SKIP: {f} (status {resp.status_code})")
                failed += 1
        except Exception as e:
            print(f"  ERR: {f} - {e}")
            failed += 1

    print(f"\nCopied {success} files, {failed} failed")

except Exception as e:
    print(f"Error copying files: {e}")

print("\n" + "=" * 60)
print("STEP 5: Invalidate CloudFront cache")
print("=" * 60)

try:
    import time
    resp = cloudfront.create_invalidation(
        DistributionId=CF_DISTRIBUTION,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/*']
            },
            'CallerReference': str(int(time.time()))
        }
    )
    print(f"Created invalidation: {resp['Invalidation']['Id']}")
except Exception as e:
    print(f"CloudFront invalidation error: {e}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
print("Wait 1-2 minutes for CloudFront cache to clear")
print("Test: https://d2f065h47nuk0c.cloudfront.net/")
