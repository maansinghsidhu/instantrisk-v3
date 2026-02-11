"""Check CloudFront frontend status"""
import requests

CF_URL = "https://d2f065h47nuk0c.cloudfront.net"

print("=" * 60)
print("Testing CloudFront Frontend")
print("=" * 60)

# Test index.html
try:
    resp = requests.get(f"{CF_URL}/", timeout=10)
    print(f"index.html status: {resp.status_code}")
    if resp.status_code == 200:
        # Check if it's the right content
        if "InstantRisk" in resp.text:
            print("  Content: InstantRisk frontend OK")
        print(f"  First 500 chars: {resp.text[:500]}")
    else:
        print(f"  Response: {resp.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

# Test some assets
assets_to_test = [
    "main.dart.js",
    "flutter.js",
    "favicon.png",
    "manifest.json",
    "canvaskit/canvaskit.js",
    "assets/fonts/MaterialIcons-Regular.otf",
]

print("\n" + "=" * 60)
print("Testing Assets")
print("=" * 60)

for asset in assets_to_test:
    try:
        resp = requests.head(f"{CF_URL}/{asset}", timeout=10)
        status = "OK" if resp.status_code == 200 else f"FAIL ({resp.status_code})"
        print(f"  {asset}: {status}")
    except Exception as e:
        print(f"  {asset}: ERROR ({e})")

print("\nDone!")
print(f"\nFrontend URL: {CF_URL}")
