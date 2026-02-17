"""Upload HTTPS fix for main.dart.js"""
import boto3
import time

# PASTE FRESH CREDENTIALS HERE:
KEY = "PASTE_ACCESS_KEY_HERE"
SECRET = "PASTE_SECRET_KEY_HERE"
TOKEN = "PASTE_SESSION_TOKEN_HERE"

print("Uploading HTTPS-fixed main.dart.js...")
s3 = boto3.client('s3', region_name='us-east-1',
                  aws_access_key_id=KEY,
                  aws_secret_access_key=SECRET,
                  aws_session_token=TOKEN)

s3.upload_file(
    r'C:\Users\maani\github-instantrisk\repo\frontend\build\web\main.dart.js',
    'instantrisk-frontend-995306061991',
    'main.dart.js',
    ExtraArgs={'ContentType': 'application/javascript', 'CacheControl': 'no-cache'}
)
print("Uploaded!")

print("Invalidating CloudFront...")
cf = boto3.client('cloudfront', region_name='us-east-1',
                  aws_access_key_id=KEY,
                  aws_secret_access_key=SECRET,
                  aws_session_token=TOKEN)
cf.create_invalidation(
    DistributionId='E33Y8KCBL4GJY',
    InvalidationBatch={
        'Paths': {'Quantity': 1, 'Items': ['/main.dart.js']},
        'CallerReference': f'https-fix-{int(time.time())}',
    }
)
print("DONE! Hard refresh (Ctrl+Shift+R) in 30-60 seconds")
