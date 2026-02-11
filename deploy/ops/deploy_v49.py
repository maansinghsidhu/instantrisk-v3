"""Deploy backend fix to ECS - v49 (UUID type fixes)"""
import boto3
import os
import zipfile
import time

# Fresh AWS credentials from user
# AWS credentials should be set via environment before running
# AWS_SECRET_ACCESS_KEY removed - set via environment
# AWS_SESSION_TOKEN removed - set via environment
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

BACKEND_DIR = r'C:\Users\maani\instantrisk-v2\backend-merged'
S3_BUCKET = 'instantrisk-pipeline-artifacts-995306061991'
ZIP_NAME = 'backend-v49.zip'

print("="*60)
print("DEPLOYING BACKEND v49 - UUID TYPE FIXES")
print("Fixed: user_id, assessment_id types across entire codebase")
print("="*60)

# Step 1: Create zip
print("\n1. Creating deployment zip...")
zip_path = os.path.join(BACKEND_DIR, ZIP_NAME)
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(BACKEND_DIR):
        # Skip unnecessary directories
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'venv', '.venv', 'chromadb_data', 'qdrant_storage', 'uploads']]
        for file in files:
            if file.endswith('.pyc') or file == ZIP_NAME:
                continue
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, BACKEND_DIR).replace(os.sep, '/')
            zf.write(file_path, arcname)
print(f"   Created: {zip_path}")

# Step 2: Upload to S3
print("\n2. Uploading to S3...")
s3 = boto3.client('s3', region_name='us-east-1')
s3.upload_file(zip_path, S3_BUCKET, f'backend/{ZIP_NAME}')
print(f"   Uploaded to s3://{S3_BUCKET}/backend/{ZIP_NAME}")

# Step 3: Start CodeBuild
print("\n3. Starting CodeBuild...")
cb = boto3.client('codebuild', region_name='us-east-1')
build = cb.start_build(
    projectName='instantrisk-backend',
    sourceTypeOverride='S3',
    sourceLocationOverride=f'{S3_BUCKET}/backend/{ZIP_NAME}'
)
build_id = build['build']['id']
print(f"   Build started: {build_id}")

# Step 4: Wait for build
print("\n4. Waiting for build to complete...")
while True:
    time.sleep(15)
    status = cb.batch_get_builds(ids=[build_id])['builds'][0]
    phase = status.get('currentPhase', 'UNKNOWN')
    build_status = status['buildStatus']
    print(f"   Phase: {phase}, Status: {build_status}")
    if build_status in ['SUCCEEDED', 'FAILED', 'STOPPED']:
        break

if build_status != 'SUCCEEDED':
    print(f"\nBuild failed! Check CodeBuild logs.")
    exit(1)

# Step 5: Register new task definition
print("\n5. Registering new task definition...")
ecs = boto3.client('ecs', region_name='us-east-1')

# Get current task def
current_task = ecs.describe_task_definition(taskDefinition='instantrisk-backend')['taskDefinition']

# Register new version
new_task = ecs.register_task_definition(
    family='instantrisk-backend',
    containerDefinitions=current_task['containerDefinitions'],
    taskRoleArn=current_task.get('taskRoleArn', ''),
    executionRoleArn=current_task['executionRoleArn'],
    networkMode=current_task['networkMode'],
    requiresCompatibilities=current_task['requiresCompatibilities'],
    cpu=current_task['cpu'],
    memory=current_task['memory'],
)
new_revision = new_task['taskDefinition']['revision']
print(f"   New revision: {new_revision}")

# Step 6: Update ECS service
print("\n6. Updating ECS service...")
ecs.update_service(
    cluster='instantrisk',
    service='instantrisk-backend',
    taskDefinition=f'instantrisk-backend:{new_revision}',
    forceNewDeployment=True
)
print("   Service updated - deploying...")

# Step 7: Wait for deployment
print("\n7. Waiting for deployment (this may take 2-3 minutes)...")
waiter = ecs.get_waiter('services_stable')
try:
    waiter.wait(
        cluster='instantrisk',
        services=['instantrisk-backend'],
        WaiterConfig={'Delay': 15, 'MaxAttempts': 20}
    )
    print("   Deployment complete!")
except Exception as e:
    print(f"   Deployment still in progress: {e}")

print("\n" + "="*60)
print("DEPLOYMENT v49 COMPLETE!")
print("="*60)
