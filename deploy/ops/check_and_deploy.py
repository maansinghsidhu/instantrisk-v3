import boto3
import json
import zipfile
import os
from io import BytesIO

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

s3 = session.client('s3')

print("=" * 60)
print("1. CHECKING S3 FOR WASM FILES")
print("=" * 60)
bucket = "instantrisk-frontend-995306061991"
try:
    for key in ["canvaskit/canvaskit.wasm", "canvaskit/skwasm.wasm"]:
        try:
            resp = s3.head_object(Bucket=bucket, Key=key)
            print(f"  {key}: {resp['ContentLength']} bytes (exists)")
        except:
            print(f"  {key}: MISSING")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("2. CREATING BACKEND DEPLOYMENT ZIP")
print("=" * 60)
backend_path = r"C:\Users\maani\instantrisk-v2\backend"
zip_buffer = BytesIO()

with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(backend_path):
        # Skip __pycache__ and .git
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv', '.venv']]
        for file in files:
            if file.endswith('.pyc'):
                continue
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, backend_path).replace(os.sep, '/')
            zf.write(file_path, arcname)
            
print(f"Created zip: {zip_buffer.tell()} bytes")

# Upload to S3
print("\n" + "=" * 60)
print("3. UPLOADING TO S3")
print("=" * 60)
zip_buffer.seek(0)
s3.put_object(
    Bucket="instantrisk-deployment-995306061991",
    Key="backend-v25.zip",
    Body=zip_buffer.getvalue()
)
print("Uploaded backend-v25.zip")

# Start CodeBuild
print("\n" + "=" * 60)
print("4. STARTING CODEBUILD")
print("=" * 60)
cb = session.client('codebuild')
try:
    resp = cb.start_build(
        projectName="instantrisk-backend",
        sourceVersion="backend-v25.zip",
        environmentVariablesOverride=[
            {'name': 'SOURCE_VERSION', 'value': 'v25', 'type': 'PLAINTEXT'}
        ]
    )
    build_id = resp['build']['id']
    print(f"Build started: {build_id}")
except Exception as e:
    print(f"CodeBuild error: {e}")
    # Try direct ECR approach
    print("Will try direct task def update instead...")

print("\nDone!")
