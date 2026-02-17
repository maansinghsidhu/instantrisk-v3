"""Quick frontend CORS fix deploy - v97.2"""
import subprocess
import boto3
import os
import time
import mimetypes

print("=" * 60)
print("QUICK FRONTEND CORS FIX - v97.2")
print("=" * 60)

# Step 1: Build Flutter web
print("\n[1/3] Building Flutter web app...")
os.chdir(r"C:\Users\maani\github-instantrisk\repo\frontend")
result = subprocess.run([r"C:\Users\maani\flutter\bin\flutter.bat", "build", "web", "--release"],
                       capture_output=True, text=True, shell=True)
if result.returncode != 0:
    print(f"Build failed: {result.stderr}")
    exit(1)
print("  Build completed successfully")

# Step 2: Upload to S3
print("\n[2/3] Uploading to S3...")
s3 = boto3.client('s3', region_name='us-east-1')

FRONTEND_BUILD = r"C:\Users\maani\github-instantrisk\repo\frontend\build\web"
S3_BUCKET = "instantrisk-frontend-995306061991"

MIME_OVERRIDES = {
    '.wasm': 'application/wasm',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.html': 'text/html',
    '.css': 'text/css',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon',
}

uploaded = 0
for root, dirs, files in os.walk(FRONTEND_BUILD):
    for fname in files:
        local_path = os.path.join(root, fname)
        s3_key = os.path.relpath(local_path, FRONTEND_BUILD).replace(os.sep, '/')

        ext = os.path.splitext(fname)[1].lower()
        content_type = MIME_OVERRIDES.get(ext) or 'application/octet-stream'

        if fname == 'index.html':
            cache_control = 'no-cache, no-store, must-revalidate'
        else:
            cache_control = 'public, max-age=31536000'

        s3.upload_file(
            local_path, S3_BUCKET, s3_key,
            ExtraArgs={
                'ContentType': content_type,
                'CacheControl': cache_control,
            }
        )
        uploaded += 1
        if uploaded % 50 == 0:
            print(f"  Uploaded {uploaded} files...")

print(f"  Total: {uploaded} files")

# Step 3: Invalidate CloudFront
print("\n[3/3] Invalidating CloudFront...")
cf = boto3.client('cloudfront', region_name='us-east-1')
invalidation = cf.create_invalidation(
    DistributionId='E33Y8KCBL4GJY',
    InvalidationBatch={
        'Paths': {'Quantity': 1, 'Items': ['/*']},
        'CallerReference': f'cors-fix-{int(time.time())}',
    }
)
print(f"  Invalidation ID: {invalidation['Invalidation']['Id']}")

print("\n" + "=" * 60)
print("FRONTEND CORS FIX DEPLOYED!")
print("  URL: https://d2ci3ptu2ygeo3.cloudfront.net")
print("  API: http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com/api/v1")
print("  Wait 2-3 minutes for CloudFront to update, then hard refresh")
print("=" * 60)
