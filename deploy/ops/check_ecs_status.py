"""Check ECS deployment status"""
import boto3
import os

# AWS credentials should be set via environment before running
# AWS_SECRET_ACCESS_KEY removed - set via environment
# AWS_SESSION_TOKEN removed - set via environment
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

ecs = boto3.client('ecs', region_name='us-east-1')

# Get service status
response = ecs.describe_services(
    cluster='instantrisk',
    services=['instantrisk-backend']
)

service = response['services'][0]
print(f"Service: {service['serviceName']}")
print(f"Status: {service['status']}")
print(f"Running count: {service['runningCount']}")
print(f"Desired count: {service['desiredCount']}")
print(f"Pending count: {service['pendingCount']}")

# Get task definition
task_def = service['taskDefinition'].split('/')[-1]
print(f"Task definition: {task_def}")

# Get deployments
print("\nDeployments:")
for deploy in service['deployments']:
    print(f"  - {deploy['status']}: {deploy['runningCount']}/{deploy['desiredCount']} (task: {deploy['taskDefinition'].split('/')[-1]})")
