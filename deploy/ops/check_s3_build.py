import boto3
import os

# AWS credentials should be set via environment before running
# AWS_SECRET_ACCESS_KEY removed - set via environment
# AWS_SESSION_TOKEN removed - set via environment

s3 = boto3.client('s3', region_name='us-east-1')

bucket = 'instantrisk-frontend-995306061991'

# Get detailed info on key files
for key in ['main.dart.js', 'index.html', 'version.json']:
    resp = s3.head_object(Bucket=bucket, Key=key)
    print(f"{key}:")
    print(f"  Size: {resp['ContentLength']} bytes")
    print(f"  Last Modified: {resp['LastModified']}")
    print()

# Get version.json content
resp = s3.get_object(Bucket=bucket, Key='version.json')
print("version.json content:")
print(resp['Body'].read().decode())
