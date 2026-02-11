import boto3
import json
import zipfile
import os
from io import BytesIO
import time

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

cb = session.client('codebuild')
s3 = session.client('s3')

# Check backend project config
print("1. CHECKING BACKEND CODEBUILD PROJECT")
try:
    resp = cb.batch_get_projects(names=['instantrisk-backend'])
    proj = resp['projects'][0]
    print(f"Source type: {proj['source']['type']}")
    print(f"Source location: {proj['source'].get('location', 'N/A')}")
    
    # Get the expected source bucket
    source_loc = proj['source'].get('location', '')
    if source_loc.startswith('arn:aws:s3'):
        # Parse bucket from ARN
        parts = source_loc.split(':::')[1].split('/')
        source_bucket = parts[0]
        print(f"Source bucket: {source_bucket}")
    elif 's3://' in source_loc:
        source_bucket = source_loc.replace('s3://', '').split('/')[0]
        print(f"Source bucket: {source_bucket}")
    else:
        source_bucket = "instantrisk-pipeline-artifacts-995306061991"
        
except Exception as e:
    print(f"Error: {e}")
    source_bucket = "instantrisk-pipeline-artifacts-995306061991"

# Create and upload zip to correct location
print("\n2. CREATING AND UPLOADING BACKEND ZIP")
backend_path = r"C:\Users\maani\instantrisk-v2\backend"
zip_buffer = BytesIO()

with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(backend_path):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv', '.venv']]
        for file in files:
            if file.endswith('.pyc'):
                continue
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, backend_path).replace(os.sep, '/')
            zf.write(file_path, arcname)
            
print(f"Created zip: {zip_buffer.tell()} bytes")

zip_buffer.seek(0)
s3.put_object(
    Bucket=source_bucket,
    Key="backend-source.zip",
    Body=zip_buffer.getvalue()
)
print(f"Uploaded to s3://{source_bucket}/backend-source.zip")

# Start build
print("\n3. STARTING CODEBUILD")
try:
    resp = cb.start_build(projectName='instantrisk-backend')
    build_id = resp['build']['id']
    print(f"Build started: {build_id}")
    
    # Wait for build
    print("\nWaiting for build to complete...")
    start_time = time.time()
    while True:
        status = cb.batch_get_builds(ids=[build_id])
        phase = status['builds'][0]['currentPhase']
        build_status = status['builds'][0]['buildStatus']
        elapsed = int(time.time() - start_time)
        print(f"  [{elapsed}s] Phase: {phase}, Status: {build_status}")
        if build_status != 'IN_PROGRESS':
            break
        time.sleep(15)
    
    print(f"\nBuild completed: {build_status}")
    
    if build_status == 'SUCCEEDED':
        # Update ECS service
        print("\n4. UPDATING ECS SERVICE")
        ecs = session.client('ecs')
        
        # Get latest task definition
        task_defs = ecs.list_task_definitions(familyPrefix='instantrisk-backend', sort='DESC')
        latest_task_def = task_defs['taskDefinitionArns'][0]
        print(f"Latest task def: {latest_task_def.split('/')[-1]}")
        
        # Update service
        resp = ecs.update_service(
            cluster='instantrisk',
            service='instantrisk-backend',
            taskDefinition=latest_task_def,
            forceNewDeployment=True
        )
        print("ECS service updated!")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\nDone!")
