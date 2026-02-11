import boto3
import json
import zipfile
import os
import time
from io import BytesIO

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

s3 = session.client('s3')
codebuild = session.client('codebuild')
ecs = session.client('ecs')
ecr = session.client('ecr')

# Find the correct S3 bucket
print("Finding S3 bucket for CodeBuild...")
buckets = s3.list_buckets()
codebuild_bucket = None
for b in buckets['Buckets']:
    name = b['Name']
    if 'codebuild' in name.lower() or 'instantrisk' in name.lower():
        print(f"  Found: {name}")
        if 'codebuild' in name.lower():
            codebuild_bucket = name

# Check CodeBuild project for source bucket
print("\nChecking CodeBuild project...")
try:
    project = codebuild.batch_get_projects(names=['instantrisk-backend'])
    if project['projects']:
        source = project['projects'][0].get('source', {})
        print(f"  Source type: {source.get('type')}")
        if source.get('type') == 'S3':
            location = source.get('location', '')
            print(f"  S3 location: {location}")
            if '/' in location:
                codebuild_bucket = location.split('/')[0]
except Exception as e:
    print(f"  Error: {e}")

if not codebuild_bucket:
    # Create the bucket
    print("\nCreating CodeBuild bucket...")
    codebuild_bucket = "instantrisk-codebuild-995306061991"
    try:
        s3.create_bucket(Bucket=codebuild_bucket)
        print(f"  Created: {codebuild_bucket}")
    except Exception as e:
        if 'BucketAlreadyOwnedByYou' in str(e):
            print(f"  Bucket exists: {codebuild_bucket}")
        else:
            print(f"  Error: {e}")
            # Use documents bucket
            codebuild_bucket = "instantrisk-documents-995306061991"
            print(f"  Using: {codebuild_bucket}")

print(f"\nUsing bucket: {codebuild_bucket}")

BACKEND_DIR = "C:/Users/maani/instantrisk-v2/backend"
S3_KEY = "backend-source.zip"

print("\n" + "=" * 60)
print("STEP 1: Create backend zip")
print("=" * 60)

zip_buffer = BytesIO()
file_count = 0
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(BACKEND_DIR):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv', '.venv']]
        for file in files:
            if file.endswith('.pyc'):
                continue
            file_path = os.path.join(root, file)
            arc_name = os.path.relpath(file_path, BACKEND_DIR).replace(os.sep, '/')
            zf.write(file_path, arc_name)
            file_count += 1
            
zip_buffer.seek(0)
print(f"Created zip: {len(zip_buffer.getvalue())} bytes, {file_count} files")

print("\n" + "=" * 60)
print("STEP 2: Upload to S3")
print("=" * 60)

s3.put_object(
    Bucket=codebuild_bucket,
    Key=S3_KEY,
    Body=zip_buffer.getvalue()
)
print(f"Uploaded to s3://{codebuild_bucket}/{S3_KEY}")

print("\n" + "=" * 60)
print("STEP 3: Start CodeBuild")
print("=" * 60)

try:
    # Update project source if needed
    codebuild.update_project(
        name='instantrisk-backend',
        source={
            'type': 'S3',
            'location': f"{codebuild_bucket}/{S3_KEY}"
        }
    )
    print("Updated CodeBuild source location")
    
    build = codebuild.start_build(projectName='instantrisk-backend')
    build_id = build['build']['id']
    print(f"Started build: {build_id}")
    
    print("\nWaiting for build...")
    while True:
        time.sleep(20)
        builds = codebuild.batch_get_builds(ids=[build_id])
        status = builds['builds'][0]['buildStatus']
        phase = builds['builds'][0].get('currentPhase', 'UNKNOWN')
        print(f"  Status: {status}, Phase: {phase}")
        
        if status == 'SUCCEEDED':
            print("\nBuild SUCCEEDED!")
            break
        elif status in ['FAILED', 'STOPPED', 'FAULT', 'TIMED_OUT']:
            print(f"\nBuild {status}!")
            logs = builds['builds'][0].get('logs', {})
            if logs.get('deepLink'):
                print(f"Logs: {logs['deepLink']}")
            break
            
except Exception as e:
    print(f"CodeBuild error: {e}")

print("\n" + "=" * 60)
print("STEP 4: Update ECS service")
print("=" * 60)

try:
    # Get latest task def
    task_defs = ecs.list_task_definitions(familyPrefix='instantrisk-backend', sort='DESC', maxResults=1)
    latest_task_arn = task_defs['taskDefinitionArns'][0]
    print(f"Latest task: {latest_task_arn.split('/')[-1]}")
    
    # Force new deployment
    ecs.update_service(
        cluster='instantrisk',
        service='instantrisk-backend',
        taskDefinition=latest_task_arn,
        forceNewDeployment=True
    )
    print("Service updated, deploying...")
    
    print("\nWaiting for deployment...")
    for i in range(24):
        time.sleep(15)
        services = ecs.describe_services(cluster='instantrisk', services=['instantrisk-backend'])
        svc = services['services'][0]
        running = svc['runningCount']
        desired = svc['desiredCount']
        deployments = len(svc['deployments'])
        print(f"  Running: {running}/{desired}, Deployments: {deployments}")
        
        if running == desired and deployments == 1:
            print("\nDeployment COMPLETE!")
            break
except Exception as e:
    print(f"ECS error: {e}")

print("\n" + "=" * 60)
print("DONE!")
print("=" * 60)
print(f"Backend: http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com")
print(f"Frontend: https://d2f065h47nuk0c.cloudfront.net")
