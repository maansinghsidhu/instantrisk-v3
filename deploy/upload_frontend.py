"""Upload frontend to S3 and invalidate CloudFront"""
import boto3
import os
import time

print("Uploading frontend to S3...")

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

        cache_control = 'no-cache' if fname == 'index.html' else 'public, max-age=31536000'

        s3.upload_file(local_path, S3_BUCKET, s3_key,
                      ExtraArgs={'ContentType': content_type, 'CacheControl': cache_control})
        uploaded += 1

print(f"Uploaded {uploaded} files")

print("Invalidating CloudFront...")
cf = boto3.client('cloudfront', region_name='us-east-1')
invalidation = cf.create_invalidation(
    DistributionId='E33Y8KCBL4GJY',
    InvalidationBatch={
        'Paths': {'Quantity': 1, 'Items': ['/*']},
        'CallerReference': f'cors-fix-{int(time.time())}',
    }
)
print(f"Done! Invalidation ID: {invalidation['Invalidation']['Id']}")
print("\nFrontend CORS fix deployed!")
print("URL: https://d2ci3ptu2ygeo3.cloudfront.net")
print("Wait 2-3 minutes for CloudFront, then hard refresh (Ctrl+Shift+R)")
