import boto3
import requests

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

print("=" * 60)
print("1. CHECKING S3 FRONTEND BUCKET - KEY FILES")
print("=" * 60)
s3 = session.client('s3')
bucket = "instantrisk-frontend-995306061991"

# Check index.html
try:
    obj = s3.get_object(Bucket=bucket, Key="index.html")
    content = obj['Body'].read().decode('utf-8')[:2000]
    print("index.html content (first 2000 chars):")
    print(content)
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("2. CHECKING EC2 FRONTEND (35.169.106.135)")
print("=" * 60)
try:
    resp = requests.get("http://35.169.106.135/", timeout=10)
    print(f"EC2 Status: {resp.status_code}")
    print(f"EC2 Content (first 1500 chars):")
    print(resp.text[:1500])
except Exception as e:
    print(f"EC2 Error: {e}")

print("\n" + "=" * 60)
print("3. CHECKING EC2 INSTANCES")
print("=" * 60)
ec2 = session.client('ec2')
try:
    instances = ec2.describe_instances(
        Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
    )
    for res in instances['Reservations']:
        for inst in res['Instances']:
            name = ""
            for tag in inst.get('Tags', []):
                if tag['Key'] == 'Name':
                    name = tag['Value']
            print(f"Instance: {name} ({inst['InstanceId']})")
            print(f"  Public IP: {inst.get('PublicIpAddress', 'N/A')}")
            print(f"  Type: {inst['InstanceType']}")
            print(f"  State: {inst['State']['Name']}")
except Exception as e:
    print(f"Error: {e}")

print("\nDone!")
