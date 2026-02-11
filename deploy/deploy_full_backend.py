"""
Deploy full backend (backend-merged) to Fargate.

This deploys the complete backend with:
- All 35+ routers
- ClaimSense + Loss Runs
- AutoGen processor
- RapidRate integration
- Subscription system
- Test users (trial, basic, premium)

Usage: python deploy_full_backend.py
"""
import boto3
import json
import time
import os
import zipfile
from datetime import datetime

# === UPDATE THESE CREDENTIALS ===
AWS_ACCESS_KEY = "PASTE_YOUR_ACCESS_KEY_HERE"
AWS_SECRET_KEY = "PASTE_YOUR_SECRET_KEY_HERE"
AWS_SESSION_TOKEN = "PASTE_YOUR_SESSION_TOKEN_HERE"
# ================================

AWS_REGION = "us-east-1"
ACCOUNT_ID = "995306061991"

# Resources
S3_BUCKET = "instantrisk-codebuild-995306061991"
ECR_REPO = "instantrisk-backend"
ECS_CLUSTER = "instantrisk"
ECS_SERVICE = "instantrisk-backend"

# Source directory
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "backend-merged")


def create_session():
    """Create boto3 session with credentials."""
    return boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        aws_session_token=AWS_SESSION_TOKEN,
        region_name=AWS_REGION
    )


def create_zip():
    """Create deployment zip from backend-merged."""
    zip_path = os.path.join(os.path.dirname(__file__), "backend-deploy.zip")

    print(f"Creating deployment zip from {BACKEND_DIR}...")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BACKEND_DIR):
            # Skip __pycache__ and .git
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.pytest_cache', 'venv']]

            for file in files:
                if file.endswith('.pyc'):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, BACKEND_DIR)
                # Use forward slashes for zip
                arcname = arcname.replace(os.sep, '/')
                zf.write(file_path, arcname)

    print(f"Created {zip_path}")
    return zip_path


def upload_to_s3(session, zip_path):
    """Upload zip to S3."""
    s3 = session.client('s3')
    key = f"backend-full-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"

    print(f"Uploading to s3://{S3_BUCKET}/{key}...")
    s3.upload_file(zip_path, S3_BUCKET, key)
    print("Upload complete")
    return key


def start_build(session, s3_key):
    """Start CodeBuild."""
    codebuild = session.client('codebuild')

    print("Starting CodeBuild...")
    response = codebuild.start_build(
        projectName='instantrisk-backend',
        sourceTypeOverride='S3',
        sourceLocationOverride=f"{S3_BUCKET}/{s3_key}",
        environmentVariablesOverride=[
            {'name': 'ECR_REPO', 'value': f"{ACCOUNT_ID}.dkr.ecr.{AWS_REGION}.amazonaws.com/{ECR_REPO}"},
        ]
    )

    build_id = response['build']['id']
    print(f"Build started: {build_id}")
    return build_id


def wait_for_build(session, build_id):
    """Wait for build to complete."""
    codebuild = session.client('codebuild')

    print("Waiting for build to complete...")
    while True:
        response = codebuild.batch_get_builds(ids=[build_id])
        build = response['builds'][0]
        status = build['buildStatus']

        if status == 'SUCCEEDED':
            print("Build SUCCEEDED!")
            return True
        elif status in ['FAILED', 'FAULT', 'TIMED_OUT', 'STOPPED']:
            print(f"Build FAILED: {status}")
            return False

        print(f"  Status: {status}...")
        time.sleep(15)


def get_latest_image(session):
    """Get latest ECR image tag."""
    ecr = session.client('ecr')

    response = ecr.describe_images(
        repositoryName=ECR_REPO,
        filter={'tagStatus': 'TAGGED'}
    )

    images = sorted(response['imageDetails'], key=lambda x: x['imagePushedAt'], reverse=True)
    if images:
        return images[0]['imageTags'][0]
    return None


def register_task_definition(session, image_tag):
    """Register new task definition."""
    ecs = session.client('ecs')

    image_uri = f"{ACCOUNT_ID}.dkr.ecr.{AWS_REGION}.amazonaws.com/{ECR_REPO}:{image_tag}"

    print(f"Registering task definition with image: {image_uri}")

    task_def = {
        'family': 'instantrisk-backend',
        'networkMode': 'awsvpc',
        'requiresCompatibilities': ['FARGATE'],
        'cpu': '512',
        'memory': '1024',
        'executionRoleArn': f'arn:aws:iam::{ACCOUNT_ID}:role/ecsTaskExecutionRole',
        'taskRoleArn': f'arn:aws:iam::{ACCOUNT_ID}:role/ecsTaskRole',
        'containerDefinitions': [
            {
                'name': 'backend',
                'image': image_uri,
                'essential': True,
                'portMappings': [{'containerPort': 8000, 'protocol': 'tcp'}],
                'environment': [
                    {'name': 'ENVIRONMENT', 'value': 'production'},
                    {'name': 'DEBUG', 'value': 'false'},
                    {'name': 'POSTGRES_HOST', 'value': 'instantrisk-db.cyjui2sqceiw.us-east-1.rds.amazonaws.com'},
                    {'name': 'POSTGRES_PORT', 'value': '5432'},
                    {'name': 'POSTGRES_DB', 'value': 'instantrisk'},
                    {'name': 'POSTGRES_USER', 'value': 'instantrisk_admin'},
                    {'name': 'POSTGRES_PASSWORD', 'value': 'InstantRisk2026!'},
                    {'name': 'REDIS_HOST', 'value': 'instantrisk-redis.mudo3b.0001.use1.cache.amazonaws.com'},
                    {'name': 'REDIS_PORT', 'value': '6379'},
                    {'name': 'QDRANT_HOST', 'value': 'instantrisk-qdrant.instantrisk.local'},
                    {'name': 'QDRANT_PORT', 'value': '6333'},
                    {'name': 'AWS_BEDROCK_REGION', 'value': 'us-east-1'},
                    {'name': 'BEDROCK_ENABLED', 'value': 'true'},
                    {'name': 'CLAIMSENSE_ENABLED', 'value': 'true'},
                    {'name': 'SECRET_KEY', 'value': 'instantrisk-secret-key-2026-production'},
                    {'name': 'JWT_SECRET_KEY', 'value': 'instantrisk-jwt-secret-2026-production'},
                ],
                'logConfiguration': {
                    'logDriver': 'awslogs',
                    'options': {
                        'awslogs-group': '/ecs/instantrisk-backend',
                        'awslogs-region': AWS_REGION,
                        'awslogs-stream-prefix': 'backend'
                    }
                },
                'linuxParameters': {'initProcessEnabled': True},
            }
        ],
    }

    response = ecs.register_task_definition(**task_def)
    revision = response['taskDefinition']['revision']
    print(f"Registered task definition: instantrisk-backend:{revision}")
    return f"instantrisk-backend:{revision}"


def update_service(session, task_def_arn):
    """Update ECS service."""
    ecs = session.client('ecs')

    print(f"Updating ECS service to use {task_def_arn}...")
    ecs.update_service(
        cluster=ECS_CLUSTER,
        service=ECS_SERVICE,
        taskDefinition=task_def_arn,
        forceNewDeployment=True
    )
    print("Service update initiated")


def wait_for_service(session):
    """Wait for service to stabilize."""
    ecs = session.client('ecs')

    print("Waiting for service to stabilize...")
    for i in range(30):
        response = ecs.describe_services(cluster=ECS_CLUSTER, services=[ECS_SERVICE])
        service = response['services'][0]

        running = service['runningCount']
        desired = service['desiredCount']
        pending = service.get('pendingCount', 0)

        print(f"  Running: {running}/{desired}, Pending: {pending}")

        if running == desired and pending == 0:
            print("Service stabilized!")
            return True

        time.sleep(10)

    print("Service did not stabilize in time")
    return False


def main():
    if "PASTE_YOUR" in AWS_ACCESS_KEY:
        print("ERROR: Please update AWS credentials in this script first!")
        print("\nGet credentials from: https://d-9067861d8b.awsapps.com/start/#")
        print("Account: Maani-Sandbox (995306061991)")
        print("Role: AWSAdministratorAccess")
        return

    session = create_session()

    # Verify credentials
    try:
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"Authenticated as: {identity['Arn']}")
    except Exception as e:
        print(f"Credential error: {e}")
        return

    # Deploy
    zip_path = create_zip()
    s3_key = upload_to_s3(session, zip_path)
    build_id = start_build(session, s3_key)

    if wait_for_build(session, build_id):
        image_tag = get_latest_image(session)
        if image_tag:
            task_def = register_task_definition(session, image_tag)
            update_service(session, task_def)
            wait_for_service(session)

            print("\n" + "=" * 60)
            print("DEPLOYMENT COMPLETE!")
            print("=" * 60)
            print("""
Test Users:
  trial.user@test.com / TestPass123  (TRIAL tier)
  basic.user@test.com / TestPass123  (BASIC tier)
  premium.user@test.com / TestPass123 (PREMIUM tier)
  demo@instantrisk.com / Demo2026pass (PREMIUM tier)

ALB: http://instantrisk-alb-307384033.us-east-1.elb.amazonaws.com
CloudFront: https://d2f065h47nuk0c.cloudfront.net
""")
        else:
            print("Could not find ECR image tag")
    else:
        print("Build failed - check CodeBuild logs")


if __name__ == "__main__":
    main()
