"""Check EC2 backend structure without data"""
import boto3, subprocess, os

# AWS credentials should be set via environment before running
# AWS_SECRET_ACCESS_KEY removed - set via environment
# AWS_SESSION_TOKEN removed - set via environment
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

INSTANCE_ID = 'i-03b49f08fa794a0c9'
EC2_IP = '35.169.106.135'
SSH_KEY = r'C:\Users\maani\.ssh\ec2_temp_key'
SSH_PUB = r'C:\Users\maani\.ssh\ec2_temp_key.pub'

def push_key():
    with open(SSH_PUB, 'r') as f:
        pub_key = f.read().strip()
    client = boto3.client('ec2-instance-connect', region_name='us-east-1')
    return client.send_ssh_public_key(InstanceId=INSTANCE_ID, InstanceOSUser='ubuntu', SSHPublicKey=pub_key)['Success']

def ssh(cmd):
    push_key()
    r = subprocess.run(['ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null', f'ubuntu@{EC2_IP}', cmd], capture_output=True, text=True, timeout=60)
    return r.stdout

print("=== EC2 Backend Structure (without data) ===\n")

# Count Python files excluding data
print("Python files (excluding data/):")
print(ssh('find /home/ubuntu/instantrisk-v2/backend -name "*.py" -not -path "*/data/*" | wc -l'))

# Size without data
print("Size without data:")
print(ssh('du -sh /home/ubuntu/instantrisk-v2/backend --exclude="*/data/*" 2>/dev/null || echo "calculating..."'))

# List app structure
print("\nDirectory structure (app/):")
print(ssh('ls -la /home/ubuntu/instantrisk-v2/backend/app/ 2>/dev/null | head -20'))

# Count routers
print("\nRouters:")
print(ssh('ls /home/ubuntu/instantrisk-v2/backend/app/routers/*.py 2>/dev/null | wc -l'))

# Count services
print("Services:")
print(ssh('ls /home/ubuntu/instantrisk-v2/backend/app/services/*.py 2>/dev/null | wc -l'))

# Count models
print("Models:")
print(ssh('ls /home/ubuntu/instantrisk-v2/backend/app/models/*.py 2>/dev/null | wc -l'))
