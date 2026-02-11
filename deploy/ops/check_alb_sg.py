"""Check ALB security groups and try alternative access"""
import boto3

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

elbv2 = session.client('elbv2')
ec2 = session.client('ec2')

print("=" * 60)
print("ALB Security Groups")
print("=" * 60)

try:
    # Find ALB
    lbs = elbv2.describe_load_balancers()
    for lb in lbs['LoadBalancers']:
        if 'instantrisk' in lb['LoadBalancerName'].lower():
            print(f"ALB: {lb['LoadBalancerName']}")
            print(f"  DNS: {lb['DNSName']}")
            print(f"  State: {lb['State']['Code']}")
            print(f"  Security Groups: {lb['SecurityGroups']}")

            # Get SG details
            for sg_id in lb['SecurityGroups']:
                sg = ec2.describe_security_groups(GroupIds=[sg_id])
                for rule in sg['SecurityGroups'][0]['IpPermissions']:
                    port = rule.get('FromPort', 'all')
                    for ip_range in rule.get('IpRanges', []):
                        print(f"    Inbound: {port} from {ip_range['CidrIp']}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("ECS Task Private IP")
print("=" * 60)

ecs = session.client('ecs')
try:
    # Get running tasks
    tasks = ecs.list_tasks(cluster='instantrisk', serviceName='instantrisk-backend')
    if tasks['taskArns']:
        task_details = ecs.describe_tasks(cluster='instantrisk', tasks=tasks['taskArns'])
        for task in task_details['tasks']:
            for attachment in task.get('attachments', []):
                for detail in attachment.get('details', []):
                    if detail['name'] == 'privateIPv4Address':
                        print(f"  Task Private IP: {detail['value']}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("EC2 Instance (Backup)")
print("=" * 60)

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
            if 'instantrisk' in name.lower():
                print(f"  {name}: {inst.get('PublicIpAddress', 'N/A')}")
except Exception as e:
    print(f"Error: {e}")
