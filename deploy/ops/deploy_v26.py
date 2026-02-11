"""Deploy backend v26 - fix DATABASE_HOST env var alias"""
import boto3
import zipfile
import os
import time
import json

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

s3 = session.client('s3')
codebuild = session.client('codebuild')
ecs = session.client('ecs')

BACKEND_DIR = r"C:\Users\maani\instantrisk-v2\backend"
S3_BUCKET = "instantrisk-documents-995306061991"
S3_KEY = "codebuild/backend-source.zip"

print("=" * 60)
print("STEP 1: Create deployment zip")
print("=" * 60)

zip_path = os.path.join(BACKEND_DIR, "deploy.zip")
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(BACKEND_DIR):
        # Skip __pycache__, .git, venv, etc.
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'venv', '.venv', 'node_modules', '.pytest_cache']]
        for file in files:
            if file.endswith(('.pyc', '.pyo', '.zip')):
                continue
            full_path = os.path.join(root, file)
            arc_name = os.path.relpath(full_path, BACKEND_DIR).replace(os.sep, '/')
            zf.write(full_path, arc_name)

print(f"Created {zip_path}")

print("\n" + "=" * 60)
print("STEP 2: Upload to S3")
print("=" * 60)

with open(zip_path, 'rb') as f:
    s3.put_object(Bucket=S3_BUCKET, Key=S3_KEY, Body=f.read())
print(f"Uploaded to s3://{S3_BUCKET}/{S3_KEY}")

print("\n" + "=" * 60)
print("STEP 3: Start CodeBuild")
print("=" * 60)

build = codebuild.start_build(projectName="instantrisk-backend")
build_id = build['build']['id']
print(f"Started build: {build_id}")

# Wait for build
print("Waiting for build to complete...")
while True:
    time.sleep(15)
    resp = codebuild.batch_get_builds(ids=[build_id])
    status = resp['builds'][0]['buildStatus']
    phase = resp['builds'][0].get('currentPhase', 'UNKNOWN')
    print(f"  Status: {status}, Phase: {phase}")
    if status != 'IN_PROGRESS':
        break

if status != 'SUCCEEDED':
    print(f"BUILD FAILED: {status}")
    exit(1)

print("BUILD SUCCEEDED!")

print("\n" + "=" * 60)
print("STEP 4: Update ECS service")
print("=" * 60)

# Force new deployment
ecs.update_service(
    cluster='instantrisk',
    service='instantrisk-backend',
    forceNewDeployment=True
)
print("ECS service update triggered")

# Wait for deployment
print("Waiting for deployment...")
time.sleep(30)

# Check status
resp = ecs.describe_services(cluster='instantrisk', services=['instantrisk-backend'])
svc = resp['services'][0]
print(f"Desired: {svc['desiredCount']}, Running: {svc['runningCount']}")
print(f"Deployments: {len(svc['deployments'])}")
for d in svc['deployments']:
    print(f"  - {d['status']}: {d['runningCount']}/{d['desiredCount']} ({d['taskDefinition'].split('/')[-1]})")

print("\n" + "=" * 60)
print("DEPLOYMENT COMPLETE")
print("=" * 60)
print("Test: https://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com/api/v1/health/live")
