import boto3, json, time, sys

REGION = 'us-east-1'

# ============================================================
# STEP 3: Upload zip to S3
# ============================================================
print('=' * 60)
print('STEP 3: Uploading backend-source.zip to S3')
print('=' * 60)

s3 = boto3.client('s3', region_name=REGION)
zip_path = r'C:\Users\maani\instantrisk-v2\backend-source.zip'
bucket = 'instantrisk-documents-995306061991'
key = 'codebuild/backend-source.zip'

s3.upload_file(zip_path, bucket, key)
print(f'Uploaded to s3://{bucket}/{key}')

resp = s3.head_object(Bucket=bucket, Key=key)
print(f'File size in S3: {resp["ContentLength"]} bytes')
print()

# ============================================================
# STEP 4: Start CodeBuild and wait for completion
# ============================================================
print('=' * 60)
print('STEP 4: Starting CodeBuild project instantrisk-backend')
print('=' * 60)

cb = boto3.client('codebuild', region_name=REGION)
build_resp = cb.start_build(projectName='instantrisk-backend')
build_id = build_resp['build']['id']
print(f'Build started: {build_id}')

while True:
    status_resp = cb.batch_get_builds(ids=[build_id])
    build = status_resp['builds'][0]
    phase = build.get('currentPhase', 'UNKNOWN')
    status = build['buildStatus']
    
    if status == 'IN_PROGRESS':
        print(f'  Status: {status} | Phase: {phase}', flush=True)
        time.sleep(15)
    else:
        print(f'  Build completed with status: {status}')
        if status != 'SUCCEEDED':
            for p in build.get('phases', []):
                ctx = p.get('contexts', [])
                msg = ctx[0]['message'] if ctx else ''
                print(f'    Phase {p["phaseType"]}: {p.get("phaseStatus", "N/A")} {msg}')
            sys.exit(1)
        break

print()
print('CodeBuild completed successfully!')
print()

# ============================================================
# STEP 5: Register new ECS task definition
# ============================================================
print('=' * 60)
print('STEP 5: Registering new ECS task definition')
print('=' * 60)

with open(r'C:\Users\maani\instantrisk-v2\backend-container-def.json', 'r') as f:
    container_defs = json.load(f)

# Update health check startPeriod to 120 seconds
for c in container_defs:
    if 'healthCheck' in c:
        c['healthCheck']['startPeriod'] = 120

ecs = boto3.client('ecs', region_name=REGION)

task_def_resp = ecs.register_task_definition(
    family='instantrisk-backend',
    taskRoleArn='arn:aws:iam::995306061991:role/instantrisk-backend-task-role',
    executionRoleArn='arn:aws:iam::995306061991:role/ecsTaskExecutionRole',
    networkMode='awsvpc',
    containerDefinitions=container_defs,
    requiresCompatibilities=['FARGATE'],
    cpu='512',
    memory='1024',
)

task_def_arn = task_def_resp['taskDefinition']['taskDefinitionArn']
revision = task_def_resp['taskDefinition']['revision']
print(f'Registered task definition: {task_def_arn}')
print(f'Revision: {revision}')
print()

# ============================================================
# STEP 6: Update ECS service with new task definition
# ============================================================
print('=' * 60)
print('STEP 6: Updating ECS service instantrisk-backend')
print('=' * 60)

update_resp = ecs.update_service(
    cluster='instantrisk',
    service='instantrisk-backend',
    taskDefinition=task_def_arn,
    forceNewDeployment=True,
)

service_name = update_resp['service']['serviceName']
print(f'Service updated: {service_name}')
print(f'Task definition: {task_def_arn}')
print(f'Desired count: {update_resp["service"]["desiredCount"]}')
print()

# ============================================================
# STEP 7: Wait for service to stabilize
# ============================================================
print('=' * 60)
print('STEP 7: Waiting for service to stabilize')
print('=' * 60)
print('This may take several minutes...', flush=True)

waiter = ecs.get_waiter('services_stable')
try:
    waiter.wait(
        cluster='instantrisk',
        services=['instantrisk-backend'],
        WaiterConfig={
            'Delay': 15,
            'MaxAttempts': 40  # 15s * 40 = 10 minutes
        }
    )
    print('Service has stabilized successfully!')
except Exception as e:
    print(f'WARNING: Waiter finished with: {e}')
    # Check current state
    desc = ecs.describe_services(cluster='instantrisk', services=['instantrisk-backend'])
    svc = desc['services'][0]
    print(f'  Running count: {svc["runningCount"]}')
    print(f'  Desired count: {svc["desiredCount"]}')
    for dep in svc.get('deployments', []):
        print(f'  Deployment {dep["id"]}: status={dep["rolloutState"]}, running={dep["runningCount"]}, desired={dep["desiredCount"]}')
    sys.exit(1)

print()
print('=' * 60)
print('DEPLOYMENT COMPLETE')
print('=' * 60)
print(f'Task Definition: {task_def_arn}')
print(f'Service: instantrisk-backend')
print(f'Cluster: instantrisk')
