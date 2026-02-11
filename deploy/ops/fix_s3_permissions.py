"""Fix S3 frontend bucket permissions for CloudFront"""
import boto3
import json

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

s3 = session.client('s3')
BUCKET = "instantrisk-frontend-995306061991"

print("=" * 60)
print("Checking current bucket configuration")
print("=" * 60)

# Check current bucket policy
try:
    policy = s3.get_bucket_policy(Bucket=BUCKET)
    print("Current policy:")
    print(json.dumps(json.loads(policy['Policy']), indent=2))
except Exception as e:
    print(f"No bucket policy: {e}")

# Check public access block
try:
    pab = s3.get_public_access_block(Bucket=BUCKET)
    print("\nPublic Access Block:")
    print(json.dumps(pab['PublicAccessBlockConfiguration'], indent=2))
except Exception as e:
    print(f"No public access block: {e}")

print("\n" + "=" * 60)
print("Setting public access for CloudFront")
print("=" * 60)

# Remove public access block
try:
    s3.delete_public_access_block(Bucket=BUCKET)
    print("Removed public access block")
except Exception as e:
    print(f"Could not remove public access block: {e}")

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
    print(f"Could not set bucket policy: {e}")

# Configure static website hosting
try:
    s3.put_bucket_website(
        Bucket=BUCKET,
        WebsiteConfiguration={
            'IndexDocument': {'Suffix': 'index.html'},
            'ErrorDocument': {'Key': 'index.html'}
        }
    )
    print("Configured static website hosting")
except Exception as e:
    print(f"Could not configure website hosting: {e}")

# Set CORS
cors_config = {
    'CORSRules': [
        {
            'AllowedHeaders': ['*'],
            'AllowedMethods': ['GET', 'HEAD'],
            'AllowedOrigins': ['*'],
            'ExposeHeaders': [],
            'MaxAgeSeconds': 3600
        }
    ]
}

try:
    s3.put_bucket_cors(Bucket=BUCKET, CORSConfiguration=cors_config)
    print("Set CORS configuration")
except Exception as e:
    print(f"Could not set CORS: {e}")

print("\n" + "=" * 60)
print("Listing some files in bucket")
print("=" * 60)

resp = s3.list_objects_v2(Bucket=BUCKET, MaxKeys=20)
for obj in resp.get('Contents', []):
    print(f"  {obj['Key']}")

print("\nDone! Try accessing https://d2f065h47nuk0c.cloudfront.net/")
