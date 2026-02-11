"""Deploy backend v54 - Fixed transaction handling in reset"""
import boto3
import os
import zipfile
import time

# AWS credentials
# AWS credentials should be set via environment before running
# AWS_SECRET_ACCESS_KEY removed - set via environment
# AWS_SESSION_TOKEN removed - set via environment
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

BACKEND_DIR = r'C:\Users\maani\instantrisk-v2\backend-merged'
S3_BUCKET = 'instantrisk-pipeline-artifacts-995306061991'
ZIP_NAME = 'backend-v54.zip'

print("="*60)
print("DEPLOYING BACKEND v54")
print("- Fixed: Separate transactions for each table in reset")
print("="*60)

# Step 1: Create zip
print("\n1. Creating deployment zip...")
zip_path = os.path.join(BACKEND_DIR, ZIP_NAME)
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(BACKEND_DIR):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'venv', '.venv', 'chromadb_data', 'qdrant_storage', 'uploads']]
        for file in files:
            if file.endswith('.pyc') or file.startswith('backend-v'):
                continue
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, BACKEND_DIR).replace(os.sep, '/')
            zf.write(file_path, arcname)
print(f"   Created: {zip_path}")

# Step 2: Upload to S3
print("\n2. Uploading to S3...")
s3 = boto3.client('s3', region_name='us-east-1')
s3.upload_file(zip_path, S3_BUCKET, f'backend/{ZIP_NAME}')
print("   Uploaded!")

# Step 3: Start CodeBuild
print("\n3. Starting CodeBuild...")
cb = boto3.client('codebuild', region_name='us-east-1')
build = cb.start_build(
    projectName='instantrisk-backend',
    sourceTypeOverride='S3',
    sourceLocationOverride=f'{S3_BUCKET}/backend/{ZIP_NAME}'
)
build_id = build['build']['id']
print(f"   Build: {build_id.split(':')[1][:8]}")

# Step 4: Wait for build
print("\n4. Waiting for build...")
while True:
    time.sleep(20)
    status = cb.batch_get_builds(ids=[build_id])['builds'][0]
    phase = status.get('currentPhase', 'UNKNOWN')
    build_status = status['buildStatus']
    print(f"   {phase}")
    if build_status in ['SUCCEEDED', 'FAILED', 'STOPPED']:
        break

if build_status != 'SUCCEEDED':
    print(f"\n[FAILED] Check CodeBuild logs")
    exit(1)
print(f"\n   Build SUCCEEDED!")

# Step 5: Update ECS
print("\n5. Updating ECS...")
ecs = boto3.client('ecs', region_name='us-east-1')
current_task = ecs.describe_task_definition(taskDefinition='instantrisk-backend')['taskDefinition']
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
rev = new_task['taskDefinition']['revision']
ecs.update_service(
    cluster='instantrisk',
    service='instantrisk-backend',
    taskDefinition=f'instantrisk-backend:{rev}',
    forceNewDeployment=True
)
print(f"   Task def v{rev} deploying...")

# Wait briefly
print("\n6. Waiting 90s for service to stabilize...")
time.sleep(90)

print("\n" + "="*60)
print("DEPLOYMENT v54 COMPLETE!")
print("="*60)
print("\nNext: Run database reset:")
print('curl -X POST "http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com/api/v1/admin/reset-database?secret=InstantRisk2026Reset!"')
