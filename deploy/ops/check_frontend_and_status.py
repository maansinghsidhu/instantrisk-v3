import boto3
import json

# AWS credentials
session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

s3 = session.client('s3')
cloudfront = session.client('cloudfront')

print("=" * 60)
print("CHECKING FRONTEND DEPLOYMENT")
print("=" * 60)

# List S3 buckets for frontend
try:
    buckets = s3.list_buckets()
    frontend_bucket = None
    for b in buckets['Buckets']:
        if 'frontend' in b['Name'].lower() or 'instantrisk' in b['Name'].lower():
            print(f"Found bucket: {b['Name']}")
            frontend_bucket = b['Name']
except Exception as e:
    print(f"Error listing buckets: {e}")

# Check frontend bucket contents
if frontend_bucket:
    print(f"\nFiles in {frontend_bucket}:")
    try:
        objects = s3.list_objects_v2(Bucket=frontend_bucket, MaxKeys=20)
        for obj in objects.get('Contents', []):
            print(f"  {obj['Key']} ({obj['Size']} bytes)")
    except Exception as e:
        print(f"Error: {e}")

# Check CloudFront distributions
print("\n" + "=" * 60)
print("CLOUDFRONT DISTRIBUTIONS")
print("=" * 60)
try:
    dists = cloudfront.list_distributions()
    for dist in dists.get('DistributionList', {}).get('Items', []):
        print(f"\nDistribution: {dist['Id']}")
        print(f"  Domain: {dist['DomainName']}")
        print(f"  Status: {dist['Status']}")
        for origin in dist.get('Origins', {}).get('Items', []):
            print(f"  Origin: {origin['DomainName']}")
except Exception as e:
    print(f"Error: {e}")

# Check ECS service status
print("\n" + "=" * 60)
print("ECS BACKEND STATUS")
print("=" * 60)
ecs = session.client('ecs')
try:
    services = ecs.describe_services(cluster='instantrisk', services=['instantrisk-backend'])
    for svc in services['services']:
        print(f"Service: {svc['serviceName']}")
        print(f"  Status: {svc['status']}")
        print(f"  Running: {svc['runningCount']}/{svc['desiredCount']}")
        print(f"  Task Def: {svc['taskDefinition'].split('/')[-1]}")
except Exception as e:
    print(f"Error: {e}")

print("\nDone!")
