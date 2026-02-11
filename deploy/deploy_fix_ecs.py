import boto3, json

REGION = 'us-east-1'
ecs = boto3.client('ecs', region_name=REGION)

# Load container definition
with open(r'C:\Users\maani\instantrisk-v2\backend-container-def.json', 'r') as f:
    container_defs = json.load(f)

# Ensure health check startPeriod is 120
for c in container_defs:
    if 'healthCheck' in c:
        c['healthCheck']['startPeriod'] = 120

# Register with CORRECT execution role from working revision 4
task_def_resp = ecs.register_task_definition(
    family='instantrisk-backend',
    taskRoleArn='arn:aws:iam::995306061991:role/instantrisk-backend-task-role',
    executionRoleArn='arn:aws:iam::995306061991:role/instantrisk-ecs-execution-role',
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

# Update service
update_resp = ecs.update_service(
    cluster='instantrisk',
    service='instantrisk-backend',
    taskDefinition=task_def_arn,
    forceNewDeployment=True,
)
print(f'Service updated with new task definition')
print(f'Desired count: {update_resp["service"]["desiredCount"]}')

# Wait for stabilization
print('Waiting for service to stabilize (this may take several minutes)...')
waiter = ecs.get_waiter('services_stable')
try:
    waiter.wait(
        cluster='instantrisk',
        services=['instantrisk-backend'],
        WaiterConfig={
            'Delay': 15,
            'MaxAttempts': 40
        }
    )
    print('Service has stabilized successfully!')
except Exception as e:
    print(f'Waiter result: {e}')
    desc = ecs.describe_services(cluster='instantrisk', services=['instantrisk-backend'])
    svc = desc['services'][0]
    print(f'  Running count: {svc["runningCount"]}')
    print(f'  Desired count: {svc["desiredCount"]}')
    for dep in svc.get('deployments', []):
        print(f'  Deployment {dep["id"]}: rollout={dep.get("rolloutState","N/A")}, running={dep["runningCount"]}, desired={dep["desiredCount"]}')

# Final status
desc = ecs.describe_services(cluster='instantrisk', services=['instantrisk-backend'])
svc = desc['services'][0]
print()
print('=' * 60)
print('DEPLOYMENT COMPLETE')
print('=' * 60)
print(f'Task Definition: {task_def_arn}')
print(f'Service: {svc["serviceName"]}')
print(f'Running: {svc["runningCount"]} / Desired: {svc["desiredCount"]}')
for dep in svc.get('deployments', []):
    print(f'  Deployment {dep["id"]}: status={dep["status"]}, rollout={dep.get("rolloutState","N/A")}, running={dep["runningCount"]}/{dep["desiredCount"]}')
events = svc.get('events', [])[:3]
for e in events:
    print(f'  [{e["createdAt"]}] {e["message"]}')
