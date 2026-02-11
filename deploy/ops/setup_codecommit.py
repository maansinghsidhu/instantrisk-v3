"""Create CodeCommit repos and push directly from EC2"""
import boto3
import subprocess
import os

# AWS credentials should be set via environment before running
# AWS_SECRET_ACCESS_KEY removed - set via environment
# AWS_SESSION_TOKEN removed - set via environment
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

cc = boto3.client('codecommit', region_name='us-east-1')

# Create repos
repos = [
    ('instantrisk-frontend', 'Flutter frontend for InstantRisk v2'),
    ('instantrisk-backend', 'FastAPI backend for InstantRisk v2'),
]

print("="*60)
print("Creating CodeCommit Repositories")
print("="*60)

for name, desc in repos:
    try:
        r = cc.create_repository(repositoryName=name, repositoryDescription=desc)
        url = r['repositoryMetadata']['cloneUrlHttp']
        print(f"Created: {name}")
        print(f"  URL: {url}")
    except cc.exceptions.RepositoryNameExistsException:
        r = cc.get_repository(repositoryName=name)
        url = r['repositoryMetadata']['cloneUrlHttp']
        print(f"Exists: {name}")
        print(f"  URL: {url}")
    except Exception as e:
        print(f"Error creating {name}: {e}")

print("\n" + "="*60)
print("Repository URLs:")
print("="*60)

# Get all repos
for name, _ in repos:
    try:
        r = cc.get_repository(repositoryName=name)
        print(f"{name}:")
        print(f"  HTTP: {r['repositoryMetadata']['cloneUrlHttp']}")
        print(f"  SSH:  {r['repositoryMetadata']['cloneUrlSsh']}")
    except Exception as e:
        print(f"Error: {e}")
