import boto3
import os

# AWS credentials should be set via environment before running
# AWS_SECRET_ACCESS_KEY removed - set via environment
# AWS_SESSION_TOKEN removed - set via environment
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

cb = boto3.client('codebuild', region_name='us-east-1')
builds = cb.list_builds_for_project(projectName='instantrisk-backend', sortOrder='DESCENDING')
if builds['ids']:
    build_id = builds['ids'][0]
    status = cb.batch_get_builds(ids=[build_id])['builds'][0]
    print(f"Build: {build_id.split(':')[-1][:8]}")
    print(f"Status: {status['buildStatus']}")
    print(f"Phase: {status.get('currentPhase', 'N/A')}")

    # Check ECS service
    ecs = boto3.client('ecs', region_name='us-east-1')
    svc = ecs.describe_services(cluster='instantrisk', services=['instantrisk-backend'])['services'][0]
    print(f"\nECS Service: {svc['status']}")
    print(f"Running tasks: {svc['runningCount']}/{svc['desiredCount']}")
    print(f"Task def: {svc['taskDefinition'].split('/')[-1]}")
