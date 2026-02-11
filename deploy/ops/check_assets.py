import boto3

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', ''),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    aws_session_token=os.environ.get('AWS_SESSION_TOKEN', ''),
    region_name="us-east-1"
)

s3 = session.client('s3')
bucket = "instantrisk-frontend-995306061991"

print("Checking for missing assets in S3...")
print("=" * 60)

# Missing assets from the errors
missing_assets = [
    "assets/assets/fonts/Inter-Medium.ttf",
    "assets/assets/fonts/Inter-Bold.ttf",
    "assets/assets/fonts/Inter-Regular.ttf",
    "assets/assets/fonts/Inter-SemiBold.ttf",
    "assets/packages/syncfusion_flutter_pdfviewer/assets/fonts/RobotoMono-Regular.ttf",
    "assets/assets/images/logo_icon.png",
    "assets/assets/images/logo_full.png",
]

for asset in missing_assets:
    try:
        s3.head_object(Bucket=bucket, Key=asset)
        print(f"  EXISTS: {asset}")
    except:
        print(f"  MISSING: {asset}")

print("\n" + "=" * 60)
print("Listing all assets/ files in S3:")
print("=" * 60)

paginator = s3.get_paginator('list_objects_v2')
for page in paginator.paginate(Bucket=bucket, Prefix='assets/'):
    for obj in page.get('Contents', []):
        print(f"  {obj['Key']} ({obj['Size']} bytes)")
