"""Fix CloudFront custom error responses that break API JSON responses"""
import boto3
import time
import os

# Fresh AWS credentials
# AWS credentials should be set via environment before running
# AWS_SECRET_ACCESS_KEY removed - set via environment
# AWS_SESSION_TOKEN removed - set via environment
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

DIST_ID = 'E27KXSCZQ10BRJ'  # Backend CloudFront distribution

print("=" * 60)
print("FIXING CLOUDFRONT CUSTOM ERROR RESPONSES")
print("Distribution: E27KXSCZQ10BRJ (d2f065h47nuk0c.cloudfront.net)")
print("=" * 60)

cf = boto3.client('cloudfront', region_name='us-east-1')

# Step 1: Get current config
print("\n1. Getting current distribution config...")
resp = cf.get_distribution_config(Id=DIST_ID)
config = resp['DistributionConfig']
etag = resp['ETag']

# Show current error responses
current_errors = config.get('CustomErrorResponses', {})
print(f"   Current CustomErrorResponses: {current_errors}")

# Step 2: Remove custom error responses
print("\n2. Removing custom error responses...")
config['CustomErrorResponses'] = {'Quantity': 0}

# Step 3: Update distribution
print("\n3. Updating distribution...")
cf.update_distribution(
    Id=DIST_ID,
    DistributionConfig=config,
    IfMatch=etag
)
print("   Distribution update initiated!")

# Step 4: Invalidate API cache
print("\n4. Invalidating /api/* cache...")
cf.create_invalidation(
    DistributionId=DIST_ID,
    InvalidationBatch={
        'Paths': {'Quantity': 1, 'Items': ['/api/*']},
        'CallerReference': str(time.time())
    }
)
print("   Cache invalidation started!")

print("\n" + "=" * 60)
print("FIX APPLIED!")
print("Wait 5-10 minutes for CloudFront to deploy changes")
print("Then test: curl https://d2f065h47nuk0c.cloudfront.net/api/v1/health/live")
print("=" * 60)
